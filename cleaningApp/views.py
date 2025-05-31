import requests
from django.utils.timezone import now
from django.db import transaction
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from common.serializers import SuccessResponseSerializer, ErrorResponseSerializer
from common.views import ListModelMixin # Import the mixin
from configs.utils import success_response, error_response
from cleaningApp.models import CleaningData
from cleaningApp.serializers import GetCleaningDataSerializer
from configs.endpoint import SOURCE_SERVICES_URL, SOURCE_SERVICES_TARGET, SOURCE_SERVICES_CLEAN

class ProcessCleaningDataSuccessResponseSerializer(SuccessResponseSerializer):
    data = GetCleaningDataSerializer(many=True, required=False, allow_null=True)

class ListCleaningDataSuccessResponseSerializer(SuccessResponseSerializer):
    data = GetCleaningDataSerializer(many=True, required=False, allow_null=True)

class CleaningDataViewSet(ListModelMixin, viewsets.ViewSet): # Add ListModelMixin
    serializer_class = GetCleaningDataSerializer

    def get_queryset(self): # Implement get_queryset
        return CleaningData.objects.all()

    def _fetch_source_data(self, url: str):
        """Fetches data from the given URL."""
        # This method will re-raise requests exceptions to be handled by the main try-except block.
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def _parse_source_response(self, raw_data_json: dict | list):
        """Parses the initial JSON response and extracts items."""
        if isinstance(raw_data_json, list):
            return raw_data_json
        elif isinstance(raw_data_json, dict) and 'data' in raw_data_json and isinstance(raw_data_json['data'], list):
            return raw_data_json['data']
        else:
            # Raise a specific error or return an indicator that the main method can use
            # For now, raising ValueError which will be caught by the generic Exception handler.
            raise ValueError("Unrecognized data structure from source API.")

    def _apply_cleaning_rules(self, content_to_save: any, rules: dict):
        """Applies cleaning rules to the content."""
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
                        new_list_data.append(record_original) # Keep non-dict items as is
                return new_list_data

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
                                cleaned_feed_list.append(feed_item_dict_original) # Keep non-dict items
                        main_dict_copy['feed'] = cleaned_feed_list
                    elif isinstance(feed_content_original, dict): # Single dict in 'feed'
                        feed_dict_copy = feed_content_original.copy()
                        for key_to_remove in feed_keys_to_remove:
                            feed_dict_copy.pop(key_to_remove, None)
                        main_dict_copy['feed'] = feed_dict_copy
                return main_dict_copy
        return content_to_save # Return original if no rules applied or type mismatch

    def _save_cleaned_item(self, source_url: str, content_to_save: any, processed_objects_map: dict):
        """Saves or updates a single cleaned item."""
        if not isinstance(content_to_save, (list, dict)): # Ensure content is JSON serializable
            # Or handle this case by logging, skipping, or converting if possible
            # For now, skip saving if content is not list/dict after cleaning
            return

        with transaction.atomic():
            obj, created = CleaningData.objects.get_or_create(
                source=source_url,
                defaults={
                    'content': content_to_save,
                    'updatedAt': now() # Set updatedAt on creation too
                }
            )
            if not created:
                obj.content = content_to_save
                obj.updatedAt = now()
                obj.save()
            processed_objects_map[source_url] = obj

    @extend_schema(
        summary="Clean and store data",
        description=("Data cleaning process"),
        tags=["Data Cleaning"],
        request=None,
        responses={
            200: OpenApiResponse(
                description="Data successfully processed and stored",
                response=ProcessCleaningDataSuccessResponseSerializer
            ),
            400: OpenApiResponse(description="Bad request", response=ErrorResponseSerializer),
            500: OpenApiResponse(description="Internal server error.", response=ErrorResponseSerializer),
            502: OpenApiResponse(description="Error from source API.", response=ErrorResponseSerializer),
            503: OpenApiResponse(description="Failed to contact source API.", response=ErrorResponseSerializer)
        }
    )
    @action(detail=False, methods=["post"], url_path="process")
    def list_simple_ingested_data(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        source_api_full_url = f"{base_url}{SOURCE_SERVICES_URL}"
        target_source_full_urls = {f"{base_url}{path}" for path in SOURCE_SERVICES_TARGET}
        processed_objects_map = {}

        try:
            raw_data_json = self._fetch_source_data(source_api_full_url)
            items = self._parse_source_response(raw_data_json)
            
            for item in items:
                if not isinstance(item, dict):
                    continue

                item_source_url = item.get("source")
                if not item_source_url or item_source_url not in target_source_full_urls:
                    continue
                
                content_to_clean = item.get("result")
                cleaned_content = content_to_clean # Default to original if no rules apply

                relative_item_path = None
                if item_source_url.startswith(base_url):
                    relative_item_path = item_source_url[len(base_url):]

                if relative_item_path and relative_item_path in SOURCE_SERVICES_CLEAN:
                    rules = SOURCE_SERVICES_CLEAN[relative_item_path]
                    cleaned_content = self._apply_cleaning_rules(content_to_clean, rules)

                self._save_cleaned_item(item_source_url, cleaned_content, processed_objects_map)
            
            saved_objects_list = list(processed_objects_map.values())
            serializer = GetCleaningDataSerializer(saved_objects_list, many=True)
            return success_response(
                data=serializer.data,
                message=f"Data for {len(saved_objects_list)} relevant sources successfully processed, cleaned, and stored.",
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
        summary="Retrieve cleaned data",
        description="Presenting cleaned data",
        tags=["Data Cleaning"],
        responses={
            200: OpenApiResponse(
                description="Cleaned data fetched successfully", 
                response=ListCleaningDataSuccessResponseSerializer
            ),
            500: OpenApiResponse(description="Internal server error.", response=ErrorResponseSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_cleaning_data(self, request):
        # The schema is preserved from the original method.
        # The core logic is now delegated to the mixin.
        # It used '-updatedAt', so we specify that.
        return self._list_all_items(request, order_by_field='-updatedAt')