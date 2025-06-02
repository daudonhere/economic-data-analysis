import requests
from django.utils.timezone import now
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from configs.utils import success_response, error_response
from ingestionApp.models import IngestionData
from ingestionApp.serializers import IngestionDataSerializer, GetIngestionDataSerializer
from rest_framework import serializers as drf_serializers
from configs.endpoint import SERVICES_URL
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.pagination import PageNumberPagination

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

class CustomPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

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
        successful_requests_data = []
        fail_logs = []

        def fetch_single_url(endpoint_path):
            full_url = f"{base_url}{endpoint_path}"
            try:
                response = requests.get(full_url, timeout=10)
                response.raise_for_status()
                json_data = response.json()

                if "data" not in json_data:
                    return {"type": "fail", "url": full_url, "error": "'data' field missing in JSON response"}

                content = json_data["data"]
                return {"type": "success", "url": full_url, "content": content}

            except requests.exceptions.Timeout:
                return {"type": "fail", "url": full_url, "error": "Request timed out"}
            except requests.exceptions.RequestException as e:
                return {"type": "fail", "url": full_url, "error": f"RequestException: {str(e)}"}
            except ValueError as e:
                return {"type": "fail", "url": full_url, "error": f"ValueError/DataError: {str(e)}"}
            except Exception as e:
                return {"type": "fail", "url": full_url, "error": f"Unexpected error: {str(e)}"}

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(fetch_single_url, endpoint): endpoint for endpoint in SERVICES_URL}
            for future in as_completed(future_to_url):
                result = future.result()
                if result["type"] == "success":
                    successful_requests_data.append(result)
                else:
                    fail_logs.append({"url": result["url"], "error": result["error"]})

        ingested_instances = []
        if successful_requests_data:
            try:
                with transaction.atomic():
                    for data_item in successful_requests_data:
                        ingested_instances.append(
                            IngestionData(
                                content=data_item["content"],
                                source=data_item["url"],
                                createdAt=now(),
                                updatedAt=now()
                            )
                        )
                    IngestionData.objects.bulk_create(ingested_instances)
            except Exception as e:
                for data_item in successful_requests_data:
                    fail_logs.append({"url": data_item["url"], "error": f"Failed to save to DB: {str(e)}"})
                successful_requests_data = []

        serialized_success_data = IngestionDataSerializer(
            IngestionData.objects.filter(source__in=[d["url"] for d in successful_requests_data]), many=True
        ).data

        if not serialized_success_data and not fail_logs:
            return success_response(
                data=[],
                message="No endpoints defined or processed.",
                code=status.HTTP_200_OK
            )

        if serialized_success_data and fail_logs:
            return success_response(
                data={
                    "message": "Partial success.",
                    "success_count": len(serialized_success_data),
                    "failed_count": len(fail_logs),
                    "failed_logs": fail_logs,
                    "ingested_data": serialized_success_data,
                },
                message="Some endpoints succeeded, others failed.",
                code=status.HTTP_207_MULTI_STATUS
            )

        if serialized_success_data:
            return success_response(
                data={"ingested_data": serialized_success_data},
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
        description="Presenting collected data with pagination",
        tags=["Data Ingestion"],
        parameters=[
            OpenApiParameter(name='page', type=OpenApiTypes.INT, description='Page number to retrieve.', default=1),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, description='Number of items per page.', default=50),
        ],
        responses={
            200: OpenApiResponse(response=ListIngestedSuccessResponseWrapperSerializer, description="Data fetched successfully."),
            500: OpenApiResponse(response=IngestionErrorResponseWrapperSerializer, description="Internal server error while fetching data.")
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_simple_ingested_data(self, request):
        try:
            queryset = IngestionData.objects.all().order_by('-createdAt')

            paginator = CustomPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            serializer = GetIngestionDataSerializer(paginated_queryset, many=True)

            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            return error_response(
                message=f"Failed to fetch data: {str(e)}",
                data=[],
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )