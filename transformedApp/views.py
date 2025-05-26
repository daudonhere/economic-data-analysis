import requests
from decimal import Decimal, ROUND_HALF_UP, DivisionByZero
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response 
from transformedApp.models import TransformedData
from transformedApp.serializers import TransformedDataSerializer

# Dependensi untuk TF-IDF
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

def extract_text_from_json_content(data_content):
    texts = []
    if isinstance(data_content, dict):
        for key, value in data_content.items():
            if isinstance(value, str):
                texts.append(value)
            elif isinstance(value, (dict, list)):
                texts.extend(extract_text_from_json_content(value))
    elif isinstance(data_content, list):
        for item in data_content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, (dict, list)):
                 texts.extend(extract_text_from_json_content(item))
    return texts


class DataTransformationViewSet(viewsets.ViewSet):
    CLEANSED_DATA_ENDPOINT_PATH = "/services/v1/cleansing/collecting"

    def _get_cleansed_data_url(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        return f"{base_url}{self.CLEANSED_DATA_ENDPOINT_PATH}"

    @extend_schema(
        summary="Process Cleansed Data and Store Transformations",
        description=(
            "Fetches data from the cleansed data endpoint, calculates TF-IDF based frequency "
            "and percentage change, then stores each item as a new TransformedData record. "
            "Requires scikit-learn for TF-IDF calculation."
        ),
        tags=["Data Transformation"],
        responses={
            200: OpenApiResponse(
                description="Data successfully transformed and stored.",
                response=TransformedDataSerializer(many=True)
            ),
            400: OpenApiResponse(description="Bad request or validation error."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="Error from the cleansed data API."),
            503: OpenApiResponse(description="Failed to contact the cleansed data API."),
            501: OpenApiResponse(description="TF-IDF calculation engine (scikit-learn) not available.")
        }
    )
    @action(detail=False, methods=["post"], url_path="process-and-store") # Menggunakan POST karena membuat resource baru
    def process_and_store_from_cleansed(self, request):
        if not SKLEARN_AVAILABLE:
            return error_response(
                message="TF-IDF calculation engine (scikit-learn) is not available on the server.",
                code=status.HTTP_501_NOT_IMPLEMENTED
            )

        cleansed_data_url = self._get_cleansed_data_url(request)
        
        try:
            response = requests.get(cleansed_data_url, timeout=20) # Timeout lebih lama mungkin diperlukan
            response.raise_for_status()
            items_from_cleansing_api = response.json() # Diasumsikan ini adalah list of dicts
            
            if not isinstance(items_from_cleansing_api, list):
                # Jika endpoint mengembalikan struktur seperti {'data': [...]}, sesuaikan di sini
                if isinstance(items_from_cleansing_api, dict) and 'data' in items_from_cleansing_api and isinstance(items_from_cleansing_api['data'], list):
                    items_from_cleansing_api = items_from_cleansing_api['data']
                else:
                    return error_response(
                        message="Unexpected data structure from cleansed data API.",
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            if not items_from_cleansing_api:
                return success_response(
                    data=[],
                    message="No data received from cleansed data API to process.",
                    code=status.HTTP_200_OK
                )

            # 1. Siapkan korpus untuk TF-IDF
            corpus_texts_for_tfidf = []
            original_contents = [] # Simpan konten asli untuk disimpan nanti

            for item_data in items_from_cleansing_api:
                # 'result' dari cleansed API adalah 'content' untuk TransformedData
                content_json = item_data.get('result') 
                original_contents.append(content_json) # Simpan JSON asli
                
                # Ekstrak teks dari JSON content untuk TF-IDF
                extracted_texts_list = extract_text_from_json_content(content_json)
                # Gabungkan semua string yang diekstrak dari satu item menjadi satu dokumen teks
                document_text = " ".join(extracted_texts_list)
                corpus_texts_for_tfidf.append(document_text)

            # 2. Hitung TF-IDF jika ada teks dalam korpus
            document_frequencies = [Decimal("0.00")] * len(items_from_cleansing_api)
            if any(corpus_texts_for_tfidf): # Hanya jalankan TF-IDF jika ada teks
                vectorizer = TfidfVectorizer()
                try:
                    tfidf_matrix = vectorizer.fit_transform(corpus_texts_for_tfidf)
                    # Hitung jumlah skor TF-IDF per dokumen sebagai 'frequency'
                    for i in range(tfidf_matrix.shape[0]):
                        # Kuantisasi ke 2 tempat desimal sesuai model
                        freq_sum = Decimal(str(tfidf_matrix[i].sum())).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        document_frequencies[i] = freq_sum
                except ValueError as e:
                    # Bisa terjadi jika korpus hanya berisi stop words atau string kosong setelah preprocessing
                    # Biarkan frekuensi sebagai 0.00 untuk kasus ini
                    # Anda bisa menambahkan logging di sini
                    # print(f"TF-IDF ValueError: {e}. Frequencies will be 0.")
                    pass


            # 3. Proses setiap item, hitung persentase, dan simpan
            created_transformed_data_objects = []
            two_decimal_places = Decimal("0.01")

            with transaction.atomic(): # Semua atau tidak sama sekali untuk batch ini
                for i, item_data in enumerate(items_from_cleansing_api):
                    current_source = item_data.get('source')
                    current_content_json = original_contents[i] # Gunakan JSON asli yang disimpan
                    current_calculated_frequency = document_frequencies[i]
                    
                    # Hitung persentase perubahan frekuensi
                    percentage_change = Decimal("0.00")
                    previous_record = TransformedData.objects.filter(source=current_source).order_by('-createdAt').first()

                    if previous_record and previous_record.frequency is not None:
                        prev_freq = previous_record.frequency
                        if prev_freq != Decimal("0.00"): # Hindari pembagian dengan nol
                            try:
                                change = ((current_calculated_frequency - prev_freq) / prev_freq) * Decimal("100.0")
                                percentage_change = change.quantize(two_decimal_places, rounding=ROUND_HALF_UP)
                            except DivisionByZero:
                                percentage_change = Decimal("0.00") # Atau nilai lain yang sesuai
                        # Jika prev_freq == 0 dan current_calculated_frequency > 0, ini adalah kenaikan tak terbatas.
                        # Anda mungkin ingin menanganinya secara khusus, misal, set ke 100% atau nilai besar.
                        # Untuk saat ini, jika prev_freq == 0, persentase tetap 0 kecuali jika Anda ingin logika lain.
                        elif current_calculated_frequency > Decimal("0.00"): # prev_freq is 0, current is > 0
                             percentage_change = Decimal("100.00") # Atau representasi lain untuk kenaikan dari 0

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
                message=f"Error from cleansed data API ({cleansed_data_url}): {e.response.status_code} - {e.response.text[:200]}",
                code=status.HTTP_502_BAD_GATEWAY
            )
        except requests.exceptions.RequestException as e:
            return error_response(
                message=f"Failed to contact cleansed data API ({cleansed_data_url}): {str(e)}",
                code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            # import traceback # Untuk debugging lebih lanjut
            # print(traceback.format_exc())
            return error_response(
                message=f"An unexpected error occurred during transformation: {str(e)}",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
