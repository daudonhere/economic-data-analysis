import requests
from django.utils.timezone import now
from django.db import transaction
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from configs.utils import success_response, error_response
from cleaningApp.models import CleaningData
from cleaningApp.serializers import GetCleaningDataSerializer
from configs.endpoint import SOURCE_SERVICES_URL, SOURCE_SERVICES_TARGET, SOURCE_SERVICES_CLEAN
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.pagination import PageNumberPagination

class CleaningSuccessResponseWrapperSerializer(drf_serializers.Serializer):
    data = GetCleaningDataSerializer(many=True, required=False, allow_null=True)
    status = drf_serializers.CharField(default="success")
    code = drf_serializers.IntegerField()
    messages = drf_serializers.CharField()

class CleaningErrorResponseWrapperSerializer(drf_serializers.Serializer):
    data = drf_serializers.JSONField(required=False, allow_null=True)
    status = drf_serializers.CharField(default="error")
    code = drf_serializers.IntegerField()
    messages = drf_serializers.CharField()

class CustomCleaningPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

class CleaningDataViewSet(viewsets.ViewSet):
    serializer_class = GetCleaningDataSerializer

    def _clean_data(self, content_to_save, relative_item_path):
        """Helper to apply cleaning rules."""
        if relative_item_path and relative_item_path in SOURCE_SERVICES_CLEAN:
            rules = SOURCE_SERVICES_CLEAN[relative_item_path]
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
        return content_to_save

    @extend_schema(
        summary="Clean and store data",
        description=("Data cleaning process"),
        tags=["Data Cleaning"],
        request=None,
        responses={
            200: OpenApiResponse(
                description="Data successfully processed and stored",
                response=CleaningSuccessResponseWrapperSerializer
            ),
            400: OpenApiResponse(description="Bad request", response=CleaningErrorResponseWrapperSerializer),
            500: OpenApiResponse(description="Internal server error.", response=CleaningErrorResponseWrapperSerializer),
            502: OpenApiResponse(description="Error from source API.", response=CleaningErrorResponseWrapperSerializer),
            503: OpenApiResponse(description="Failed to contact source API.", response=CleaningErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["post"], url_path="process")
    def process_and_clean_data(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        source_api_full_url = f"{base_url}{SOURCE_SERVICES_URL}"
        target_source_full_urls = {f"{base_url}{path}" for path in SOURCE_SERVICES_TARGET}
        
        try:
            response = requests.get(source_api_full_url, timeout=30) # Increased timeout for potentially large ingestion data
            response.raise_for_status()
            raw_data_json = response.json()

            items = []
            if isinstance(raw_data_json, list):
                items = raw_data_json
            elif isinstance(raw_data_json, dict) and 'data' in raw_data_json and isinstance(raw_data_json['data'], list):
                items = raw_data_json['data']
            else:
                return error_response(
                    message="Unrecognized data structure from source API.",
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            objects_to_create_or_update = []
            sources_processed = set()

            for item in items:
                if not isinstance(item, dict):
                    continue

                item_source_url = item.get("source")
                if item_source_url in target_source_full_urls:
                    content_to_save = item.get("result")
                    
                    relative_item_path = None
                    if item_source_url.startswith(base_url):
                        relative_item_path = item_source_url[len(base_url):]
                    
                    cleaned_content = self._clean_data(content_to_save, relative_item_path)

                    if isinstance(cleaned_content, (list, dict)):
                        objects_to_create_or_update.append({
                            'source': item_source_url,
                            'content': cleaned_content
                        })
                        sources_processed.add(item_source_url)
            
            with transaction.atomic():
                current_time = now()
                for obj_data in objects_to_create_or_update:
                    obj, created = CleaningData.objects.update_or_create(
                        source=obj_data['source'],
                        defaults={
                            'content': obj_data['content'],
                            'updatedAt': current_time,
                            'createdAt': obj_data['createdAt'] if not created else current_time
                        }
                    )
            
            saved_objects_list = CleaningData.objects.filter(source__in=sources_processed).order_by('-updatedAt')
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
        description="Presenting cleaned data with pagination",
        tags=["Data Cleaning"],
        parameters=[
            OpenApiParameter(name='page', type=OpenApiTypes.INT, description='Page number to retrieve.', default=1),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, description='Number of items per page.', default=50),
        ],
        responses={
            200: OpenApiResponse(
                description="Cleaned data fetched successfully",
                response=CleaningSuccessResponseWrapperSerializer
            ),
            500: OpenApiResponse(description="Internal server error.", response=CleaningErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_cleaning_data(self, request):
        try:
            queryset = CleaningData.objects.all().order_by('-updatedAt')

            paginator = CustomCleaningPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            serializer = GetCleaningDataSerializer(paginated_queryset, many=True)

            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            return error_response(
                message=f"Failed to fetch cleaning data: {str(e)}",
                data=[],
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )