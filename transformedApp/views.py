import requests
from decimal import Decimal, ROUND_HALF_UP, DivisionByZero
from django.db import transaction
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response 
from transformedApp.models import TransformedData
from transformedApp.serializers import TransformedDataSerializer

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class BaseCustomResponseWrapperSerializer(drf_serializers.Serializer):
    status = drf_serializers.CharField()
    code = drf_serializers.IntegerField()
    messages = drf_serializers.CharField()

class TransformedDataListSuccessResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = TransformedDataSerializer(many=True, required=False, allow_null=True)
    status = drf_serializers.CharField(default="success")

class CustomErrorResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
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
        for item_element in data_content: # Renamed 'item' to 'item_element' to avoid conflict
            if isinstance(item_element, str):
                texts.append(item_element)
            elif isinstance(item_element, (dict, list)):
                 texts.extend(extract_text_from_json_content(item_element))
    return texts

class DataTransformationViewSet(viewsets.ViewSet):
    CLEANING_DATA_ENDPOINT_PATH = "/services/v1/cleaning/collecting"

    def _get_cleaning_data_url(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        return f"{base_url}{self.CLEANING_DATA_ENDPOINT_PATH}"

    @extend_schema(
        summary="A. Process Cleaning Data and Store Transformations",
        description=(
            "Fetches data from the cleaning data endpoint, calculates TF-IDF based frequency "
            "and percentage change, then stores each item as a new TransformedData record. "
            "Requires scikit-learn for TF-IDF calculation."
        ),
        tags=["3. Data Transformation"],
        responses={
            200: OpenApiResponse(
                description="Data successfully transformed and stored.",
                response=TransformedDataListSuccessResponseWrapperSerializer
            ),
            400: OpenApiResponse(description="Bad request or validation error.", response=CustomErrorResponseWrapperSerializer),
            500: OpenApiResponse(description="Internal server error.", response=CustomErrorResponseWrapperSerializer),
            502: OpenApiResponse(description="Error from the cleaning data API.", response=CustomErrorResponseWrapperSerializer),
            503: OpenApiResponse(description="Failed to contact the cleaning data API.", response=CustomErrorResponseWrapperSerializer),
            501: OpenApiResponse(description="TF-IDF calculation engine (scikit-learn) not available.", response=CustomErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["post"], url_path="process")
    def process_and_store_from_cleaning(self, request):
        if not SKLEARN_AVAILABLE:
            return error_response(
                message="TF-IDF calculation engine (scikit-learn) is not available on the server.",
                code=status.HTTP_501_NOT_IMPLEMENTED
            )

        cleaning_data_url = self._get_cleaning_data_url(request)
        
        try:
            response = requests.get(cleaning_data_url, timeout=20)
            response.raise_for_status()
            items_from_cleaning_api = response.json()
            
            if not isinstance(items_from_cleaning_api, list):
                if isinstance(items_from_cleaning_api, dict) and 'data' in items_from_cleaning_api and isinstance(items_from_cleaning_api['data'], list):
                    items_from_cleaning_api = items_from_cleaning_api['data']
                else:
                    return error_response(
                        message="Unexpected data structure from cleaning data API.",
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            if not items_from_cleaning_api:
                return success_response(
                    data=[],
                    message="No data received from cleaning data API to process.",
                    code=status.HTTP_200_OK
                )

            corpus_texts_for_tfidf = []
            original_contents = []

            for item_data in items_from_cleaning_api:
                content_json = item_data.get('result') 
                original_contents.append(content_json)
                
                extracted_texts_list = extract_text_from_json_content(content_json)
                document_text = " ".join(extracted_texts_list)
                corpus_texts_for_tfidf.append(document_text)

            document_frequencies = [Decimal("0.00")] * len(items_from_cleaning_api)
            if any(corpus_texts_for_tfidf):
                vectorizer = TfidfVectorizer()
                try:
                    tfidf_matrix = vectorizer.fit_transform(corpus_texts_for_tfidf)
                    for i in range(tfidf_matrix.shape[0]):
                        freq_sum = Decimal(str(tfidf_matrix[i].sum())).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        document_frequencies[i] = freq_sum
                except ValueError as e:
                    pass

            created_transformed_data_objects = []
            two_decimal_places = Decimal("0.01")

            with transaction.atomic():
                for i, item_data in enumerate(items_from_cleaning_api):
                    current_source = item_data.get('source')
                    current_content_json = original_contents[i]
                    current_calculated_frequency = document_frequencies[i]
                    
                    percentage_change = Decimal("0.00")
                    previous_record = TransformedData.objects.filter(source=current_source).order_by('-createdAt').first()

                    if previous_record and previous_record.frequency is not None:
                        prev_freq = previous_record.frequency
                        if prev_freq != Decimal("0.00"):
                            try:
                                change = ((current_calculated_frequency - prev_freq) / prev_freq) * Decimal("100.0")
                                percentage_change = change.quantize(two_decimal_places, rounding=ROUND_HALF_UP)
                            except DivisionByZero:
                                percentage_change = Decimal("0.00")
                        elif current_calculated_frequency > Decimal("0.00"):
                             percentage_change = Decimal("100.00")

                    new_transformed_entry = TransformedData.objects.create(
                        content=current_content_json,
                        source=current_source,
                        frequency=current_calculated_frequency,
                        percentage=percentage_change
                    )
                    created_transformed_data_objects.append(new_transformed_entry)
            
            serializer = TransformedDataSerializer(created_transformed_data_objects, many=True)
            return success_response(
                data=serializer.data,
                message=f"Successfully processed and stored {len(created_transformed_data_objects)} new transformed data records.",
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
        summary="B. Retrieve Transformed Data",
        description="Fetches and returns a list of all transformed data records.",
        tags=["3. Data Transformation"],
        responses={
            200: OpenApiResponse(
                description="Transformed data fetched successfully.",
                response=TransformedDataListSuccessResponseWrapperSerializer
            ),
            500: OpenApiResponse(description="Internal server error.", response=CustomErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_transformed_data(self, request):
        try:
            queryset = TransformedData.objects.all().order_by('-createdAt')
            serializer = TransformedDataSerializer(queryset, many=True)
            return success_response(
                data=serializer.data,
                message="Transformed data fetched successfully.",
                code=status.HTTP_200_OK
            )
        except Exception as e:
            return error_response(
                message=f"Failed to fetch transformed data: {str(e)}",
                data=[],
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )