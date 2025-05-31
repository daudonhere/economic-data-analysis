import requests
from decimal import Decimal, ROUND_HALF_UP, DivisionByZero
from django.db import transaction
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from common.serializers import SuccessResponseSerializer, ErrorResponseSerializer
from common.views import ListModelMixin # Import the mixin
from configs.utils import success_response, error_response 
from transformationApp.models import TransformationData
from transformationApp.serializers import TransformationDataSerializer
from configs.endpoint import SERVICES_TRANSFORMATION_PATH

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class ProcessTransformationSuccessResponseSerializer(SuccessResponseSerializer):
    data = TransformationDataSerializer(many=True, required=False, allow_null=True)

class ListTransformationSuccessResponseSerializer(SuccessResponseSerializer):
    data = TransformationDataSerializer(many=True, required=False, allow_null=True)

from common.utils import extract_text_from_json_content # Import the moved function

class DataTransformationViewSet(ListModelMixin, viewsets.ViewSet): # Add ListModelMixin
    serializer_class = TransformationDataSerializer

    def get_queryset(self): # Implement get_queryset
        return TransformationData.objects.all()

    def _fetch_cleaning_data(self, url: str):
        """Fetches data from the cleaning app API."""
        # Re-raises exceptions to be caught by the main handler
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        items_from_cleaning_api = response.json()

        if not isinstance(items_from_cleaning_api, list):
            if isinstance(items_from_cleaning_api, dict) and \
               'data' in items_from_cleaning_api and \
               isinstance(items_from_cleaning_api['data'], list):
                return items_from_cleaning_api['data']
            else:
                raise ValueError("Unexpected data structure from cleaning data API.")
        return items_from_cleaning_api

    def _prepare_corpus_and_content(self, items_from_cleaning_api: list):
        """Prepares corpus for TF-IDF and stores original content."""
        corpus_texts_for_tfidf = []
        original_contents = []
        for item_data in items_from_cleaning_api:
            content_json = item_data.get('result')
            original_contents.append(content_json)

            extracted_texts_list = extract_text_from_json_content(content_json)
            document_text = " ".join(extracted_texts_list)
            corpus_texts_for_tfidf.append(document_text)
        return corpus_texts_for_tfidf, original_contents

    def _calculate_tfidf_frequencies(self, corpus_texts_for_tfidf: list, num_items: int):
        """Calculates TF-IDF frequencies for the corpus."""
        document_frequencies = [Decimal("0.00")] * num_items
        if any(corpus_texts_for_tfidf) and SKLEARN_AVAILABLE:
            vectorizer = TfidfVectorizer()
            try:
                tfidf_matrix = vectorizer.fit_transform(corpus_texts_for_tfidf)
                for i in range(tfidf_matrix.shape[0]):
                    freq_sum = Decimal(str(tfidf_matrix[i].sum())).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    document_frequencies[i] = freq_sum
            except ValueError:
                # Handles cases like empty vocabulary, etc. Frequencies remain 0.00.
                pass
        return document_frequencies

    def _calculate_percentage_change(self, current_source: str, current_frequency: Decimal):
        """Calculates percentage change from the previous record."""
        percentage_change = Decimal("0.00")
        two_decimal_places = Decimal("0.01")
        previous_record = TransformationData.objects.filter(source=current_source).order_by('-createdAt').first()

        if previous_record and previous_record.frequency is not None:
            prev_freq = previous_record.frequency
            if prev_freq != Decimal("0.00"):
                try:
                    change = ((current_frequency - prev_freq) / prev_freq) * Decimal("100.0")
                    percentage_change = change.quantize(two_decimal_places, rounding=ROUND_HALF_UP)
                except DivisionByZero:
                    percentage_change = Decimal("0.00") # Should not happen if prev_freq is not 0.00
            elif current_frequency > Decimal("0.00"):
                 percentage_change = Decimal("100.00") # From 0 to positive
        return percentage_change

    def _save_transformation_item(self, source: str, content: any, frequency: Decimal, percentage_change: Decimal):
        """Creates and saves a TransformationData instance."""
        new_entry = TransformationData.objects.create(
            content=content,
            source=source,
            frequency=frequency,
            percentage=percentage_change
        )
        return new_entry

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
                response=ProcessTransformationSuccessResponseSerializer
            ),
            400: OpenApiResponse(description="Bad request or validation error.", response=ErrorResponseSerializer),
            500: OpenApiResponse(description="Internal server error.", response=ErrorResponseSerializer),
            502: OpenApiResponse(description="Error from the cleaning data API.", response=ErrorResponseSerializer),
            503: OpenApiResponse(description="Failed to contact the cleaning data API.", response=ErrorResponseSerializer),
            501: OpenApiResponse(description="TF-IDF calculation engine (scikit-learn) not available.", response=ErrorResponseSerializer)
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
        created_transformation_data_objects = []

        try:
            items_from_cleaning_api = self._fetch_cleaning_data(cleaning_data_url)

            if not items_from_cleaning_api:
                return success_response(
                    data=[],
                    message="No data received from cleaning data API to process.",
                    code=status.HTTP_200_OK
                )

            corpus_texts_for_tfidf, original_contents = self._prepare_corpus_and_content(items_from_cleaning_api)

            document_frequencies = self._calculate_tfidf_frequencies(corpus_texts_for_tfidf, len(items_from_cleaning_api))

            with transaction.atomic():
                for i, item_data in enumerate(items_from_cleaning_api):
                    current_source = item_data.get('source')
                    current_content_json = original_contents[i]
                    current_calculated_frequency = document_frequencies[i]
                    
                    percentage_change = self._calculate_percentage_change(current_source, current_calculated_frequency)

                    new_entry = self._save_transformation_item(
                        source=current_source,
                        content=current_content_json,
                        frequency=current_calculated_frequency,
                        percentage_change=percentage_change
                    )
                    created_transformation_data_objects.append(new_entry)
            
            serializer = TransformationDataSerializer(created_transformation_data_objects, many=True)
            return success_response(
                data=serializer.data,
                message=f"Successfully processed and stored {len(created_transformation_data_objects)} new transformation data records.",
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
        description="Retrieve a list of all transformation data records",
        tags=["Data Transformation"],
        responses={
            200: OpenApiResponse(
                description="Transformation data fetched successfully.",
                response=ListTransformationSuccessResponseSerializer
            ),
            500: OpenApiResponse(description="Internal server error.", response=ErrorResponseSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_transformation_data(self, request):
        # The schema is preserved from the original method.
        # The core logic is now delegated to the mixin.
        # Default ordering by '-createdAt' in mixin matches original.
        return self._list_all_items(request)