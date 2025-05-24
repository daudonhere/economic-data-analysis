import requests
from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response
from configs.serializers import GetIngestionDataSerializer


class CleansedDataViewSet(viewsets.ViewSet):
    SOURCE_API_URL_PATH = "/services/v1/ingestion/collecting"
    FILTER_BY_SOURCE_ENDPOINT = "/services/v1/finance/sector"

    @extend_schema(
        summary="Fetch cleansed data and filter by specific source",
        description=(
            "Fetches data from the ingestion endpoint, filters items where 'source' matches "
            "the finance/sector endpoint, and serializes the result."
        ),
        tags=["Data Processing"],
        responses={
            200: OpenApiResponse(
                description="Successfully fetched, filtered, and serialized data.",
                response=GetIngestionDataSerializer(many=True)
            ),
            400: OpenApiResponse(description="Bad request or validation error from serializer."),
            500: OpenApiResponse(description="Failed to fetch or process data."),
            502: OpenApiResponse(description="Error from the source API.")
        }
    )
    @action(detail=False, methods=["get"], url_path="collecting")
    def list_simple_ingested_data(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        source_api_full_url = f"{base_url}{self.SOURCE_API_URL_PATH}"
        filter_by_source_value = f"{base_url}{self.FILTER_BY_SOURCE_ENDPOINT}"

        try:
            response = requests.get(source_api_full_url, timeout=10)
            response.raise_for_status()
            raw_data_json = response.json()
            items_to_filter = []
            if isinstance(raw_data_json, list):
                items_to_filter = raw_data_json
            elif isinstance(raw_data_json, dict) and 'data' in raw_data_json and isinstance(raw_data_json['data'], list):
                items_to_filter = raw_data_json['data']
            else:
                return error_response(
                    message="Unexpected data structure from source API.",
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            filtered_data_dicts = [
                item for item in items_to_filter
                if isinstance(item, dict) and item.get("source") == filter_by_source_value
            ]
            serializer = GetIngestionDataSerializer(data=filtered_data_dicts, many=True)
            if serializer.is_valid(raise_exception=True):
                return success_response(
                    data=serializer.data,
                    message="Data fetched, filtered, and serialized successfully.",
                    code=status.HTTP_200_OK
                )

        except requests.exceptions.HTTPError as e:
            return error_response(
                message=f"Error from source API ({source_api_full_url}): {e.response.status_code} - {e.response.text}",
                code=status.HTTP_502_BAD_GATEWAY
            )
        except requests.exceptions.RequestException as e:
            return error_response(
                message=f"Failed to connect to source API ({source_api_full_url}): {str(e)}",
                code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            return error_response(
                message=f"An unexpected error occurred: {str(e)}",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
