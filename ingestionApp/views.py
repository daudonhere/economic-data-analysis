from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.utils.timezone import now
from ingestionApp.models import IngestionData
from ingestionApp.serializers import IngestionDataSerializer, GetIngestionDataSerializer
from configs.utils import success_response, error_response
import requests


class IngestionDataViewSet(viewsets.ViewSet):
    ENDPOINTS = [
        "/services/v1/economy/fiscal",
        "/services/v1/economy/macro",
        "/services/v1/economy/monetary",
        "/services/v1/finance/crypto",
        "/services/v1/finance/downtrend",
        "/services/v1/finance/sector",
        "/services/v1/finance/stocks",
        "/services/v1/finance/volume",
    ]

    @extend_schema(
        summary="Fetch and store data",
        description="Fetches 'data' field (dict or list) from internal endpoints and stores it",
        tags=["Data Processing"],
        responses={
            200: OpenApiResponse(response=IngestionDataSerializer(many=True), description="All data ingested successfully."),
            207: OpenApiResponse(description="Partial success. Some endpoints failed."),
            500: OpenApiResponse(description="All API calls failed.")
        }
    )
    @action(detail=False, methods=["get"], url_path="storing")
    def fetch_and_store_all_api_data(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        success_data = []
        fail_logs = []

        for endpoint in self.ENDPOINTS:
            full_url = f"{base_url}{endpoint}"
            try:
                response = requests.get(full_url)
                response.raise_for_status()
                json_data = response.json()

                if "data" not in json_data:
                    raise ValueError("'data' field missing")

                content = json_data["data"]

                instance = IngestionData.objects.create(
                    content=content,
                    source=full_url,
                    createdAt=now(),
                    updatedAt=now()
                )
                serializer = IngestionDataSerializer(instance)
                success_data.append(serializer.data)

            except Exception as e:
                fail_logs.append({"url": full_url, "error": str(e)})

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
        summary="Get ingested data",
        description="Returns a list of ingested data",
        tags=["Data Processing"],
        responses={200: OpenApiResponse(response=GetIngestionDataSerializer(many=True))}
    )
    @action(detail=False, methods=["get"], url_path="collecting")
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