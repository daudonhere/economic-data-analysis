import requests
from decimal import Decimal, ROUND_HALF_UP, DivisionByZero
from django.db import transaction
from django.utils.timezone import now
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from configs.utils import success_response, error_response
from transformationApp.models import TransformationData
from transformationApp.serializers import TransformationDataSerializer
from configs.endpoint import SERVICES_TRANSFORMATION_PATH
from rest_framework.pagination import PageNumberPagination

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class BaseCustomResponseWrapperSerializer(drf_serializers.Serializer):
    status = drf_serializers.CharField()
    code = drf_serializers.IntegerField()
    messages = drf_serializers.CharField()

class TransformationDataListSuccessResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = TransformationDataSerializer(many=True, required=False, allow_null=True)
    status = drf_serializers.CharField(default="success")

class TransformationErrorResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = drf_serializers.JSONField(required=False, allow_null=True)
    status = drf_serializers.CharField(default="error")

def extract_text_from_json_content(data_content):
    texts = []
    if isinstance(data_content, dict):
        for key, value in data_content.items():
            if isinstance(value, str):
                texts.append(value)
            elif isinstance(value, (dict, list)):
                texts.extend(extract_text_from_json_content(value))
    elif isinstance(data_content, list):
        for item_element in data_content:
            if isinstance(item_element, str):
                texts.append(item_element)
            elif isinstance(item_element, (dict, list)):
                 texts.extend(extract_text_from_json_content(item_element))
    return texts

class CustomTransformationPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

class DataTransformationViewSet(viewsets.ViewSet):
    serializer_class = TransformationDataSerializer

    def _get_cleaning_data_url(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        return f"{base_url}{SERVICES_TRANSFORMATION_PATH}"

    @extend_schema(
        summary="Process transform data and store transformations",
        description=("Retrieve data and calculates TF-IDF based frequency"),
        tags=["Data Transformation"],
        request=None,
        responses={
            200: OpenApiResponse(
                description="Data successfully transformed and stored",
                response=TransformationDataListSuccessResponseWrapperSerializer
            ),
            400: OpenApiResponse(description="Bad request or validation error.", response=TransformationErrorResponseWrapperSerializer),
            500: OpenApiResponse(description="Internal server error.", response=TransformationErrorResponseWrapperSerializer),
            502: OpenApiResponse(description="Error from the cleaning data API.", response=TransformationErrorResponseWrapperSerializer),
            503: OpenApiResponse(description="Failed to contact the cleaning data API.", response=TransformationErrorResponseWrapperSerializer),
            501: OpenApiResponse(description="TF-IDF calculation engine (scikit-learn) not available.", response=TransformationErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["post"], url_path="process")
    def process_and_store_from_cleaning(self, request):
        if not SKLEARN_AVAILABLE:
            return error_response(
                message="TF-IDF calculation engine (scikit-learn) is not available on the server. Please install scikit-learn.",
                code=status.HTTP_501_NOT_IMPLEMENTED
            )

        cleaning_data_url = self._get_cleaning_data_url(request)
        
        try:
            # Request cleaning data with pagination to limit memory usage
            all_items_from_cleaning_api = []
            page = 1
            while True:
                paginated_cleaning_url = f"{cleaning_data_url}?page={page}&page_size=500" # Fetch in chunks
                response = requests.get(paginated_cleaning_url, timeout=30) # Increased timeout
                response.raise_for_status()
                paginated_response_data = response.json()

                current_page_items = []
                if isinstance(paginated_response_data, list):
                    current_page_items = paginated_response_data
                elif isinstance(paginated_response_data, dict) and 'results' in paginated_response_data and isinstance(paginated_response_data['results'], list):
                    current_page_items = paginated_response_data['results']
                else:
                    return error_response(
                        message="Unexpected paginated data structure from cleaning data API.",
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                if not current_page_items:
                    break # No more data

                all_items_from_cleaning_api.extend(current_page_items)
                
                # Check for next page, if API supports pagination
                if isinstance(paginated_response_data, dict) and 'next' in paginated_response_data and paginated_response_data['next']:
                    page += 1
                else:
                    break # No next page

            if not all_items_from_cleaning_api:
                return success_response(
                    data=[],
                    message="No data received from cleaning data API to process.",
                    code=status.HTTP_200_OK
                )

            corpus_texts_for_tfidf = []
            original_contents = []
            source_urls = []

            for item_data in all_items_from_cleaning_api:
                content_json = item_data.get('result')
                source_url = item_data.get('source')
                
                original_contents.append(content_json)
                source_urls.append(source_url)
                
                extracted_texts_list = extract_text_from_json_content(content_json)
                document_text = " ".join(extracted_texts_list)
                corpus_texts_for_tfidf.append(document_text)

            document_frequencies = [Decimal("0.00")] * len(all_items_from_cleaning_api)
            if any(corpus_texts_for_tfidf):
                vectorizer = TfidfVectorizer()
                try:
                    tfidf_matrix = vectorizer.fit_transform(corpus_texts_for_tfidf)
                    for i in range(tfidf_matrix.shape[0]):
                        # Using np.sum if tfidf_matrix is a sparse matrix, or directly sum
                        if hasattr(tfidf_matrix[i], 'sum'):
                            freq_sum = Decimal(str(tfidf_matrix[i].sum())).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        else: # Fallback for dense matrices
                            freq_sum = Decimal(str(sum(tfidf_matrix[i]))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        document_frequencies[i] = freq_sum
                except ValueError as e:
                    # Handle cases where fit_transform might fail (e.g., all empty documents)
                    pass

            transformation_objects_to_create = []
            two_decimal_places = Decimal("0.01")
            current_time = now()
            
            # Fetch existing records to calculate percentage change in bulk
            # Using select_for_update if transaction isolation is high, but not strictly needed for this logic.
            # Filtering by source_urls to limit the lookup.
            existing_records = {
                rec.source: rec
                for rec in TransformationData.objects.filter(source__in=source_urls)
                                                .order_by('source', '-createdAt') # Order to get most recent per source
                                                .distinct('source') # Only pick the latest for each source
            }


            for i, _ in enumerate(all_items_from_cleaning_api):
                current_source = source_urls[i]
                current_content_json = original_contents[i]
                current_calculated_frequency = document_frequencies[i]
                
                percentage_change = Decimal("0.00")
                previous_record = existing_records.get(current_source) # Get the most recent existing record

                if previous_record and previous_record.frequency is not None:
                    prev_freq = previous_record.frequency
                    if prev_freq != Decimal("0.00"):
                        try:
                            change = ((current_calculated_frequency - prev_freq) / prev_freq) * Decimal("100.0")
                            percentage_change = change.quantize(two_decimal_places, rounding=ROUND_HALF_UP)
                        except DivisionByZero:
                            percentage_change = Decimal("0.00")
                    elif current_calculated_frequency > Decimal("0.00"):
                         percentage_change = Decimal("100.00") # From 0 to a positive value

                transformation_objects_to_create.append(
                    TransformationData(
                        content=current_content_json,
                        source=current_source,
                        frequency=current_calculated_frequency,
                        percentage=percentage_change,
                        createdAt=current_time,
                        updatedAt=current_time
                    )
                )
            
            with transaction.atomic():
                TransformationData.objects.bulk_create(transformation_objects_to_create)
            
            # Fetch newly created objects for serialization. Filtering by `createdAt` to capture only newly created ones.
            # This assumes that `createdAt` for the batch is the same, which is set by `current_time`.
            serialized_data = TransformationDataSerializer(
                TransformationData.objects.filter(createdAt=current_time, source__in=source_urls), many=True
            ).data

            return success_response(
                data=serialized_data,
                message=f"Successfully processed and stored {len(transformation_objects_to_create)} new transformation data records.",
                code=status.HTTP_200_OK
            )

        except requests.exceptions.HTTPError as e:
            return error_response(
                message=f"Error from cleaning data API ({cleaning_data_url}): {e.response.status_code} - {e.response.text[:200]}",
                code=status.HTTP_502_BAD_GATEWAY
            )
        except requests.exceptions.RequestException as e:
            return error_response(
                message=f"Failed to contact cleaning data API ({cleaning_data_url}): {str(e)}",
                code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            return error_response(
                message=f"An unexpected error occurred during transformation: {str(e)}",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Retrieve transformation data",
        description="Retrieve a list of all transformation data records with pagination",
        tags=["Data Transformation"],
        parameters=[
            OpenApiParameter(name='page', type=OpenApiTypes.INT, description='Page number to retrieve.', default=1),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, description='Number of items per page.', default=50),
        ],
        responses={
            200: OpenApiResponse(
                description="Transformation data fetched successfully.",
                response=TransformationDataListSuccessResponseWrapperSerializer
            ),
            500: OpenApiResponse(description="Internal server error.", response=TransformationErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_transformation_data(self, request):
        try:
            queryset = TransformationData.objects.all().order_by('-createdAt')
            
            paginator = CustomTransformationPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            serializer = TransformationDataSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            return error_response(
                message=f"Failed to fetch transformation data: {str(e)}",
                data=[],
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )