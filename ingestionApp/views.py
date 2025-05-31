import requests
from django.utils.timezone import now
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response
from ingestionApp.models import IngestionData
from ingestionApp.serializers import IngestionDataSerializer, GetIngestionDataSerializer
from rest_framework import serializers as drf_serializers
from configs.endpoint import SERVICES_URL

class BaseCustomResponseWrapperSerializer(drf_serializers.Serializer):
    status = drf_serializers.CharField()
    code = drf_serializers.IntegerField()
    messages = drf_serializers.CharField()

class IngestedDataPayloadSerializer(drf_serializers.Serializer):
    ingested_data = IngestionDataSerializer(many=True)

class FetchStore200ResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = IngestedDataPayloadSerializer()
    status = drf_serializers.CharField(default="success")

class FailedLogEntrySerializer(drf_serializers.Serializer):
    url = drf_serializers.URLField()
    error = drf_serializers.CharField()

class IngestedDataPartialPayloadSerializer(drf_serializers.Serializer):
    message = drf_serializers.CharField()
    success_count = drf_serializers.IntegerField()
    failed_count = drf_serializers.IntegerField()
    failed_logs = FailedLogEntrySerializer(many=True)
    ingested_data = IngestionDataSerializer(many=True)

class FetchStore207ResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = IngestedDataPartialPayloadSerializer()
    status = drf_serializers.CharField(default="success") 

class ListIngestedSuccessResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = GetIngestionDataSerializer(many=True)
    status = drf_serializers.CharField(default="success")

class IngestionErrorResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = drf_serializers.JSONField(required=False, allow_null=True)
    status = drf_serializers.CharField(default="error")


class IngestionDataViewSet(viewsets.ViewSet):
    serializer_class = IngestionDataSerializer
    @extend_schema(
        summary="Collect and store data",
        description="Collect all data sources and store them",
        tags=["Data Ingestion"],
        request=None,
        responses={
            200: OpenApiResponse(response=FetchStore200ResponseWrapperSerializer, description="All data ingested successfully."),
            207: OpenApiResponse(response=FetchStore207ResponseWrapperSerializer, description="Partial success, some endpoints failed."),
            500: OpenApiResponse(response=IngestionErrorResponseWrapperSerializer, description="All API calls failed.")
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
            200: OpenApiResponse(response=ListIngestedSuccessResponseWrapperSerializer, description="Data fetched successfully."),
            500: OpenApiResponse(response=IngestionErrorResponseWrapperSerializer, description="Internal server error while fetching data.")
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_simple_ingested_data(self, request):
        try:
            queryset = IngestionData.objects.all().order_by('-createdAt')
            serializer = GetIngestionDataSerializer(queryset, many=True)

            return success_response(
                data=serializer.data,
                message="Data fetched successfully.",
                code=status.HTTP_200_OK
            )

        except Exception as e:
            return error_response(
                message=f"Failed to fetch data: {str(e)}",
                data=[],
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )