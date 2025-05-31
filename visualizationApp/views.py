import requests
from decimal import Decimal # Keep for any direct Decimal usage if any, though most moved
from collections import Counter, defaultdict # Keep for defaultdict if used directly, though most moved
import numpy as np # Keep for np.arange if used directly, though most moved
# from scipy import stats as scipy_stats # No longer directly used here
from django.db import transaction
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from common.serializers import SuccessResponseSerializer, ErrorResponseSerializer
from common.utils import calculate_descriptive_stats # Import moved function
from common.views import ListModelMixin # Import the mixin
from configs.utils import success_response, error_response 
from visualizationApp.models import VisualizationData
from visualizationApp.serializers import VisualizationDataSerializer
from visualizationApp.services import AnalysisService # Import the new service
from configs.endpoint import SERVICES_VISUALIZATION_PATH
import requests # Ensure requests is imported

class AnalyzeAdvancedSuccessResponseSerializer(SuccessResponseSerializer):
    data = VisualizationDataSerializer(required=False, allow_null=True)

class ListVisualizationAnalysisSuccessResponseSerializer(SuccessResponseSerializer):
    data = VisualizationDataSerializer(many=True, required=False, allow_null=True)

class VisualizationAnalysisViewSet(ListModelMixin, viewsets.ViewSet): # Add ListModelMixin
    serializer_class = VisualizationDataSerializer
    NUM_PREVIOUS_RUNS_FOR_TREND = 5 # This could be a setting or config

    def get_queryset(self): # Implement get_queryset
        return VisualizationData.objects.all()

    def _get_source_data_url(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        return f"{base_url}{SERVICES_VISUALIZATION_PATH}"

    # _get_interpretation is now part of AnalysisService

    @extend_schema(
        summary="Analyze and perform statistical tests and store insights",
        description=("Retrieve data from transformation endpoint and performs comprehensive analysis including"),
        tags=["Data Visualization & Analysis"],
        request=None, 
        responses={
            201: OpenApiResponse(
                description="Analysis complete, insights and statistical tests performed and stored.",
                response=AnalyzeAdvancedSuccessResponseSerializer
            ),
            200: OpenApiResponse( 
                description="No data from transformation endpoint to analyze, or no previous analysis to compare. Basic analysis record created.",
                response=AnalyzeAdvancedSuccessResponseSerializer
            ),
            400: OpenApiResponse(description="Bad request.", response=ErrorResponseSerializer),
            500: OpenApiResponse(description="Internal server error.", response=ErrorResponseSerializer),
            502: OpenApiResponse(description="Error from the transformation data API.", response=ErrorResponseSerializer),
            503: OpenApiResponse(description="Failed to contact the transformation data API.", response=ErrorResponseSerializer),
        }
    )
    @action(detail=False, methods=["post"], url_path="analyze")
    def analyze_and_store_insights_advanced(self, request):
        source_data_url = self._get_source_data_url(request)
        
        try:
            # Step 1: Fetch data from the transformation endpoint
            response = requests.get(source_data_url, timeout=20)
            response.raise_for_status()
            response_json = response.json()
            transformed_items_list = response_json.get("data", []) # Assuming data is under 'data' key
            
            if not isinstance(transformed_items_list, list):
                 return error_response(message="Unexpected data structure from transformation data API.", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Step 2: Handle empty transformed_items_list
            if not transformed_items_list:
                with transaction.atomic():
                    # Use common.utils.calculate_descriptive_stats for empty stats
                    empty_stats = calculate_descriptive_stats([])
                    analysis_obj = VisualizationData.objects.create(
                        analyzed_endpoint=source_data_url,
                        input_transformed_data=[],
                        all_phrases_analysis=[],
                        global_frequency_stats=empty_stats,
                        global_percentage_stats=empty_stats,
                        per_source_stats={},
                        probabilistic_insights={"notes": "No source data to process for advanced probability."},
                        inferential_stats_summary={"notes": "No source data for comparison or inferential tests."}
                    )
                return success_response(data=VisualizationDataSerializer(analysis_obj).data, message="No data from transformation API. Empty analysis record created.", code=status.HTTP_200_OK)

            # Step 3: Fetch previous analyses for comparison and trend
            previous_analysis_for_comparison = VisualizationData.objects.order_by('-createdAt').first()
            # Correctly fetch N-1 items for historical trend, ensuring not to include the current run's potential data or the one used for direct comparison if they are the same
            # The service will handle the logic of combining current data with historical trend data.
            # Querying up to NUM_PREVIOUS_RUNS_FOR_TREND, and the service can slice/use as needed.
            recent_analyses_qs = list(VisualizationData.objects.order_by('-createdAt')[:self.NUM_PREVIOUS_RUNS_FOR_TREND])


            # Step 4: Instantiate and run AnalysisService
            service = AnalysisService(
                transformed_items_list=transformed_items_list,
                previous_analysis_qs_for_trend=recent_analyses_qs, # Pass the full list for service to manage
                previous_analysis_for_comparison=previous_analysis_for_comparison
            )
            analysis_results = service.run_analysis()

            # Step 5: Create VisualizationData object
            with transaction.atomic():
                analysis_result_obj = VisualizationData.objects.create(
                    analyzed_endpoint=source_data_url,
                    input_transformed_data=transformed_items_list, # Storing the input
                    all_phrases_analysis=analysis_results["all_phrases_analysis"],
                    global_frequency_stats=analysis_results["global_frequency_stats"],
                    global_percentage_stats=analysis_results["global_percentage_stats"],
                    per_source_stats=analysis_results["per_source_stats"],
                    probabilistic_insights=analysis_results["probabilistic_insights"],
                    inferential_stats_summary=analysis_results["inferential_stats_summary"]
                )
            
            serializer = VisualizationDataSerializer(analysis_result_obj)
            return success_response(
                data=serializer.data,
                message=f"Advanced analysis complete. Insights from {len(transformed_items_list)} items stored, compared with previous run.",
                code=status.HTTP_201_CREATED
            )
        except Exception as e:
            return error_response(message=f"Error saving analysis results: {str(e)}", code=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @extend_schema(
        summary="Retrieve stored visualization analysis",
        description="Fetches and returns a list of all stored analysis results.",
        tags=["Data Visualization & Analysis"],
        responses={
            200: OpenApiResponse(description="Analysis results fetched successfully.", response=ListVisualizationAnalysisSuccessResponseSerializer),
            500: OpenApiResponse(description="Internal server error.", response=ErrorResponseSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_analysis_results(self, request):
        # The schema is preserved from the original method.
        # The core logic is now delegated to the mixin.
        # Default ordering by '-createdAt' in mixin matches original.
        return self._list_all_items(request)