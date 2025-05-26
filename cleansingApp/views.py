import requests
from django.utils.timezone import now
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response
from cleansingApp.models import CleansedData
from cleansingApp.serializers import GetCleansedDataSerializer


class CleansedDataViewSet(viewsets.ViewSet):
    SOURCE_API_URL_PATH = "/services/v1/ingestion/collecting"
    TARGET_SOURCE_PATHS_RELATIVE = [
        "/services/v1/economy/fiscal",
        "/services/v1/economy/macro",
        "/services/v1/economy/monetary",
        "/services/v1/finance/crypto",
        "/services/v1/finance/downtrend",
        "/services/v1/finance/sector",
        "/services/v1/finance/stocks",
        "/services/v1/finance/volume",
    ]
    SOURCE_CLEANING_RULES = {
        "/services/v1/finance/volume": {
            "type": "list_of_dicts",
            "keys_to_remove": ["symbol"]
        },
        "/services/v1/finance/stocks": {
            "type": "list_of_dicts",
            "keys_to_remove": ["type", "symbol", "exchangeShortName"]
        },
        "/services/v1/finance/downtrend": {
            "type": "list_of_dicts",
            "keys_to_remove": ["symbol"]
        },
        "/services/v1/finance/crypto": {
            "type": "list_of_dicts",
            "keys_to_remove": ["symbol", "stockExchange", "exchangeShortName"]
        },
        "/services/v1/economy/monetary": {
            "type": "dict_with_feed",
            "feed_keys_to_remove": ["url", "source", "author", "authors", "banner_image", "source_domain"]
        },
        "/services/v1/economy/fiscal": {
            "type": "dict_with_feed",
            "feed_keys_to_remove": ["url", "source", "author", "authors", "banner_image", "source_domain"]
        },
        "/services/v1/economy/macro": {
            "type": "dict_with_feed",
            "feed_keys_to_remove": ["url", "source", "author", "authors", "banner_image", "source_domain"]
        },
    }

    @extend_schema(
        summary="Clean & Stored Ingested Data",
        description=(
            "Fetch data from the ingestion endpoint and clensing"
        ),
        tags=["Data Processing"],
        responses={
            200: OpenApiResponse(
                description="Data Successfully Fetched",
                response=GetCleansedDataSerializer(many=True)
            ),
            400: OpenApiResponse(description="Bad request / Validation Error."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="Error from source API."),
            503: OpenApiResponse(description="Failed to contact source API.")
        }
    )
    @action(detail=False, methods=["get"], url_path="storing")
    def list_simple_ingested_data(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        source_api_full_url = f"{base_url}{self.SOURCE_API_URL_PATH}"
        target_source_full_urls = {f"{base_url}{path}" for path in self.TARGET_SOURCE_PATHS_RELATIVE}

        try:
            response = requests.get(source_api_full_url, timeout=10)
            response.raise_for_status()
            raw_data_json = response.json()

            if isinstance(raw_data_json, list):
                items = raw_data_json
            elif isinstance(raw_data_json, dict) and 'data' in raw_data_json and isinstance(raw_data_json['data'], list):
                items = raw_data_json['data']
            else:
                return error_response(
                    message="Unrecognized data structure from source API.",
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            processed_objects_map = {}

            for item in items:
                if not isinstance(item, dict):
                    continue

                item_source_url = item.get("source")
                
                if item_source_url in target_source_full_urls:
                    content_to_save = item.get("result")
                    
                    relative_item_path = None
                    if item_source_url.startswith(base_url):
                        relative_item_path = item_source_url[len(base_url):]
                    
                    if relative_item_path and relative_item_path in self.SOURCE_CLEANING_RULES:
                        rules = self.SOURCE_CLEANING_RULES[relative_item_path]
                        rule_type = rules.get("type")

                        if rule_type == "list_of_dicts" and isinstance(content_to_save, list):
                            keys_to_remove = rules.get("keys_to_remove", [])
                            if keys_to_remove:
                                new_list_data = []
                                for record_original in content_to_save:
                                    if isinstance(record_original, dict):
                                        record_copy = record_original.copy()
                                        for key in keys_to_remove:
                                            record_copy.pop(key, None)
                                        new_list_data.append(record_copy)
                                    else:
                                        new_list_data.append(record_original)
                                content_to_save = new_list_data
                        
                        elif rule_type == "dict_with_feed" and isinstance(content_to_save, dict):
                            feed_keys_to_remove = rules.get("feed_keys_to_remove", [])
                            if feed_keys_to_remove:
                                main_dict_copy = content_to_save.copy()
                                
                                if 'feed' in main_dict_copy:
                                    feed_content_original = main_dict_copy['feed']

                                    if isinstance(feed_content_original, list):
                                        cleaned_feed_list = []
                                        for feed_item_dict_original in feed_content_original:
                                            if isinstance(feed_item_dict_original, dict):
                                                feed_item_copy = feed_item_dict_original.copy()
                                                for key_to_remove in feed_keys_to_remove:
                                                    feed_item_copy.pop(key_to_remove, None)
                                                cleaned_feed_list.append(feed_item_copy)
                                            else:
                                                cleaned_feed_list.append(feed_item_dict_original)
                                        main_dict_copy['feed'] = cleaned_feed_list
                                    
                                    elif isinstance(feed_content_original, dict):
                                        feed_dict_copy = feed_content_original.copy()
                                        for key_to_remove in feed_keys_to_remove:
                                            feed_dict_copy.pop(key_to_remove, None)
                                        main_dict_copy['feed'] = feed_dict_copy
                                content_to_save = main_dict_copy

                    if isinstance(content_to_save, (list, dict)):
                        with transaction.atomic():
                            obj, created = CleansedData.objects.get_or_create(
                                source=item_source_url,
                                defaults={
                                    'content': content_to_save,
                                    'updatedAt': now()
                                }
                            )
                            if not created:
                                obj.content = content_to_save
                                obj.updatedAt = now()
                                obj.save()
                            processed_objects_map[item_source_url] = obj
            
            saved_objects_list = list(processed_objects_map.values())
            serializer = GetCleansedDataSerializer(saved_objects_list, many=True)
            return success_response(
                data=serializer.data,
                message=f"Data for {len(saved_objects_list)} relevant sources successfully processed, cleaned, and stored/updated.",
                code=status.HTTP_200_OK
            )

        except requests.exceptions.HTTPError as e:
            error_message = f"Error from source API ({source_api_full_url}): {e.response.status_code}"
            if e.response and e.response.text:
                error_message += f" - {e.response.text[:500]}"
            return error_response(message=error_message, code=status.HTTP_502_BAD_GATEWAY)
        except requests.exceptions.RequestException as e:
            return error_response(message=f"Failed to contact source API ({source_api_full_url}): {str(e)}", code=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            return error_response(message=f"An unexpected error occurred: {str(e)}", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @extend_schema(
        summary="Get cleansed data",
        description="Returns a list of cleansed data",
        tags=["Data Processing"],
        responses={200: OpenApiResponse(response=GetCleansedDataSerializer(many=True))}
    )
    @action(detail=False, methods=["get"], url_path="collecting")
    def list_cleansed_data(self, request):
        try:
            queryset = CleansedData.objects.all().order_by('-updatedAt')
            serializer = GetCleansedDataSerializer(queryset, many=True)

            return success_response(
                data=serializer.data,
                message="Cleansed data fetched successfully.",
                code=status.HTTP_200_OK
            )

        except Exception as e:
            return error_response(
                message=f"Failed to fetch cleansed data: {str(e)}",
                data=[],
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            