import requests
from django.utils.timezone import now
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from common.serializers import SuccessResponseSerializer, ErrorResponseSerializer
from common.views import ListModelMixin # Import the mixin
from configs.utils import success_response, error_response
from ingestionApp.models import IngestionData
from ingestionApp.serializers import IngestionDataSerializer, GetIngestionDataSerializer
from rest_framework import serializers as drf_serializers
from configs.endpoint import SERVICES_URL

# Payload serializers - these define the structure of the 'data' field
class IngestedDataPayloadSerializer(drf_serializers.Serializer):
    ingested_data = IngestionDataSerializer(many=True)

class FailedLogEntrySerializer(drf_serializers.Serializer):
    url = drf_serializers.URLField()
    error = drf_serializers.CharField()

class IngestedDataPartialPayloadSerializer(drf_serializers.Serializer):
    message = drf_serializers.CharField()
    success_count = drf_serializers.IntegerField()
    failed_count = drf_serializers.IntegerField()
    failed_logs = FailedLogEntrySerializer(many=True)
    ingested_data = IngestionDataSerializer(many=True)

# Response wrapper serializers using common.serializers
class FetchStore200CustomResponseSerializer(SuccessResponseSerializer):
    data = IngestedDataPayloadSerializer()

class FetchStore207CustomResponseSerializer(SuccessResponseSerializer):
    data = IngestedDataPartialPayloadSerializer()

class ListIngestedDataSuccessCustomSerializer(SuccessResponseSerializer):
    data = GetIngestionDataSerializer(many=True)

class IngestionDataViewSet(ListModelMixin, viewsets.ViewSet): # Add ListModelMixin
    # serializer_class for the ViewSet, used by ListModelMixin.
    # The 'process' action uses IngestionDataSerializer explicitly for its instances.
    serializer_class = GetIngestionDataSerializer

    def get_queryset(self): # Implement get_queryset
        return IngestionData.objects.all()

    @extend_schema(
        summary="Collect and store data",
        description="Collect all data sources and store them",
        tags=["Data Ingestion"],
        request=None,
        responses={
            200: OpenApiResponse(response=FetchStore200CustomResponseSerializer, description="All data ingested successfully."),
            207: OpenApiResponse(response=FetchStore207CustomResponseSerializer, description="Partial success, some endpoints failed."),
            500: OpenApiResponse(response=ErrorResponseSerializer, description="All API calls failed.")
        }
    )
    @action(detail=False, methods=["post"], url_path="process")
    def fetch_and_store_all_api_data(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        success_data = []
        fail_logs = []

        for endpoint in SERVICES_URL:
            full_url = f"{base_url}{endpoint}"
            try:
                response = requests.get(full_url)
                response.raise_for_status()
                json_data = response.json()

                if "data" not in json_data:
                    fail_logs.append({"url": full_url, "error": "'data' field missing in JSON response"})
                    continue 

                content = json_data["data"]
                with transaction.atomic():
                    instance = IngestionData.objects.create(
                        content=content,
                        source=full_url,
                        createdAt=now(), 
                        updatedAt=now()  
                    )
                serializer = IngestionDataSerializer(instance)
                success_data.append(serializer.data)

            except requests.exceptions.RequestException as e:
                fail_logs.append({"url": full_url, "error": f"RequestException: {str(e)}"})
            except ValueError as e:
                fail_logs.append({"url": full_url, "error": f"ValueError/DataError: {str(e)}"})
            except Exception as e: 
                fail_logs.append({"url": full_url, "error": f"Unexpected error: {str(e)}"})
        
        if not success_data and not fail_logs:
             return success_response(
                data=[],
                message="No endpoints defined or processed.",
                code=status.HTTP_200_OK 
            )

        if success_data and fail_logs:
            return success_response(
                data={
                    "message": "Partial success.",
                    "success_count": len(success_data),
                    "failed_count": len(fail_logs),
                    "failed_logs": fail_logs,
                    "ingested_data": success_data,
                },
                message="Some endpoints succeeded, others failed.",
                code=status.HTTP_207_MULTI_STATUS
            )

        if success_data:
            return success_response(
                data={"ingested_data": success_data},
                message="All data ingested successfully",
                code=status.HTTP_200_OK
            )

        return error_response(
            message="All requests failed. See logs for details.",
            data={"failed_logs": fail_logs},
            code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
    @extend_schema(
        summary="Retrieve ingested data",
        description="Presenting collected data",
        tags=["Data Ingestion"],
        responses={
            200: OpenApiResponse(response=ListIngestedDataSuccessCustomSerializer, description="Data fetched successfully."),
            500: OpenApiResponse(response=ErrorResponseSerializer, description="Internal server error while fetching data.")
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_simple_ingested_data(self, request):
        # The schema is preserved from the original method.
        # The core logic is now delegated to the mixin.
        # Default ordering by '-createdAt' in mixin matches original.
        return self._list_all_items(request)