import requests
from decimal import Decimal, ROUND_HALF_UP
from collections import Counter, defaultdict
import numpy as np
from scipy import stats as scipy_stats
from django.db import transaction
from django.utils.timezone import now
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from configs.utils import success_response, error_response
from visualizationApp.models import VisualizationData
from visualizationApp.serializers import VisualizationDataSerializer
from configs.endpoint import SERVICES_VISUALIZATION_PATH
from rest_framework.pagination import PageNumberPagination

class BaseCustomResponseWrapperSerializer(drf_serializers.Serializer):
    status = drf_serializers.CharField()
    code = drf_serializers.IntegerField()
    messages = drf_serializers.CharField()

class SingleVisualizationDataResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = VisualizationDataSerializer(required=False, allow_null=True)
    status = drf_serializers.CharField(default="success")

class ListVisualizationDataResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = VisualizationDataSerializer(many=True, required=False, allow_null=True)
    status = drf_serializers.CharField(default="success")

class VisualizationErrorResponseWrapperSerializer(BaseCustomResponseWrapperSerializer):
    data = drf_serializers.JSONField(required=False, allow_null=True)
    status = drf_serializers.CharField(default="error")

def extract_all_strings_from_json(data_content):
    strings = []
    if isinstance(data_content, dict):
        for value in data_content.values():
            if isinstance(value, str):
                strings.append(value)
            elif isinstance(value, (dict, list)):
                strings.extend(extract_all_strings_from_json(value))
    elif isinstance(data_content, list):
        for item_element in data_content:
            if isinstance(item_element, str):
                strings.append(item_element)
            elif isinstance(item_element, (dict, list)):
                strings.extend(extract_all_strings_from_json(item_element))
    return strings

def calculate_descriptive_stats(data_list):
    if not data_list:
        return {"mean": None, "median": None, "std_dev": None, "variance": None, "count": 0, "min": None, "max": None, "sum": None}

    # Ensure data is numeric and convert to float for numpy
    valid_data = [float(x) for x in data_list if x is not None and isinstance(x, (int, float, Decimal))]
    if not valid_data:
        return {"mean": None, "median": None, "std_dev": None, "variance": None, "count": 0, "min": None, "max": None, "sum": None}

    arr = np.array(valid_data, dtype=float)
    
    # Handle cases where std is 0 (e.g., all values are same)
    std_dev = np.std(arr)
    variance = np.var(arr)

    return {
        "mean": round(np.mean(arr), 4),
        "median": round(np.median(arr), 4),
        "std_dev": round(std_dev, 4),
        "variance": round(variance, 4),
        "count": len(valid_data),
        "min": round(np.min(arr), 4),
        "max": round(np.max(arr), 4),
        "sum": round(np.sum(arr), 4),
    }

class CustomVisualizationPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

class VisualizationAnalysisViewSet(viewsets.ViewSet):
    serializer_class = VisualizationDataSerializer
    NUM_PREVIOUS_RUNS_FOR_TREND = 5 # Constant for clarity

    def _get_source_data_url(self, request):
        base_url = request.build_absolute_uri('/')[:-1]
        return f"{base_url}{SERVICES_VISUALIZATION_PATH}"

    def _get_interpretation(self, p_value, alpha=0.05, test_type="general"):
        if p_value is None:
            return "Test not performed or not applicable."
        if p_value < alpha:
            return f"Significant result (p < {alpha}): Indicates a statistically significant {test_type}."
        else:
            return f"Not significant (p >= {alpha}): No statistically significant {test_type} detected."

    @extend_schema(
        summary="Analyze and perform statistical tests and store insights",
        description=("Retrieve data from transformation endpoint and performs comprehensive analysis including"),
        tags=["Data Visualization & Analysis"],
        request=None,
        responses={
            201: OpenApiResponse(
                description="Analysis complete, insights and statistical tests performed and stored.",
                response=SingleVisualizationDataResponseWrapperSerializer
            ),
            200: OpenApiResponse(
                description="No data from transformation endpoint to analyze, or no previous analysis to compare. Basic analysis record created.",
                response=SingleVisualizationDataResponseWrapperSerializer
            ),
            400: OpenApiResponse(description="Bad request.", response=VisualizationErrorResponseWrapperSerializer),
            500: OpenApiResponse(description="Internal server error.", response=VisualizationErrorResponseWrapperSerializer),
            502: OpenApiResponse(description="Error from the transformation data API.", response=VisualizationErrorResponseWrapperSerializer),
            503: OpenApiResponse(description="Failed to contact the transformation data API.", response=VisualizationErrorResponseWrapperSerializer),
        }
    )
    @action(detail=False, methods=["post"], url_path="analyze")
    def analyze_and_store_insights_advanced(self, request):
        source_data_url = self._get_source_data_url(request)

        try:
            # Fetch data from transformation API with pagination
            all_transformed_items = []
            page = 1
            while True:
                paginated_url = f"{source_data_url}?page={page}&page_size=500" # Fetch in chunks
                response = requests.get(paginated_url, timeout=60) # Increased timeout for large data pulls
                response.raise_for_status()
                paginated_response_data = response.json()

                current_page_items = []
                if isinstance(paginated_response_data, list):
                    current_page_items = paginated_response_data
                elif isinstance(paginated_response_data, dict) and 'results' in paginated_response_data and isinstance(paginated_response_data['results'], list):
                    current_page_items = paginated_response_data['results']
                else:
                    return error_response(
                        message="Unexpected paginated data structure from transformation data API.",
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                if not current_page_items:
                    break # No more data

                all_transformed_items.extend(current_page_items)

                if isinstance(paginated_response_data, dict) and 'next' in paginated_response_data and paginated_response_data['next']:
                    page += 1
                else:
                    break # No next page

            if not all_transformed_items:
                with transaction.atomic():
                    analysis_obj = VisualizationData.objects.create(
                        analyzed_endpoint=source_data_url,
                        input_transformed_data=[], # Store only what's necessary or summary
                        all_phrases_analysis=[],
                        global_frequency_stats=calculate_descriptive_stats([]),
                        global_percentage_stats=calculate_descriptive_stats([]),
                        per_source_stats={},
                        probabilistic_insights={"notes": "No source data to process for advanced probability."},
                        inferential_stats_summary={"notes": "No source data for comparison or inferential tests."}
                    )
                return success_response(data=VisualizationDataSerializer(analysis_obj).data, message="No data from transformation API. Empty analysis record created.", code=status.HTTP_200_OK)

            # --- Data Extraction and Initial Processing ---
            all_extracted_phrases_from_all_items = []
            source_phrase_details = defaultdict(lambda: {"phrases_counter": Counter(), "total_phrases_in_source": 0})
            all_frequencies_from_items = []
            all_percentages_from_items = []
            per_source_frequencies_map = defaultdict(list)
            per_source_percentages_map = defaultdict(list)

            # Pre-process data in a single loop
            for item in all_transformed_items:
                content_json, source_url = item.get('content'), item.get('source')
                item_freq, item_perc = item.get('frequency'), item.get('percentage')

                if item_freq is not None:
                    try:
                        val = Decimal(str(item_freq))
                        all_frequencies_from_items.append(val)
                        if source_url: per_source_frequencies_map[source_url].append(val)
                    except (TypeError, ValueError): pass # Silently skip invalid frequency values
                if item_perc is not None:
                    try:
                        val = Decimal(str(item_perc))
                        all_percentages_from_items.append(val)
                        if source_url: per_source_percentages_map[source_url].append(val)
                    except (TypeError, ValueError): pass # Silently skip invalid percentage values

                phrases = extract_all_strings_from_json(content_json)
                all_extracted_phrases_from_all_items.extend(phrases)
                if source_url:
                    source_phrase_details[source_url]["phrases_counter"].update(phrases)
                    source_phrase_details[source_url]["total_phrases_in_source"] += len(phrases)

            # --- Global Phrase Analysis ---
            global_phrase_counts = Counter(all_extracted_phrases_from_all_items)
            current_all_phrases_analysis_list = []
            total_phrases_overall_count = sum(global_phrase_counts.values())

            for phrase, count in global_phrase_counts.items():
                s_details = []
                for src, details in source_phrase_details.items():
                    c_in_s = details["phrases_counter"].get(phrase, 0)
                    if c_in_s > 0:
                        percentage_in_source = round((Decimal(c_in_s) / Decimal(details["total_phrases_in_source"])) * Decimal(100), 2) if details["total_phrases_in_source"] > 0 else Decimal('0.00')
                        s_details.append({"source_url": src, "count_in_source": c_in_s, "percentage_in_source": percentage_in_source})
                global_probability_percent = round((Decimal(count) / Decimal(total_phrases_overall_count)) * Decimal(100), 2) if total_phrases_overall_count > 0 else Decimal('0.00')
                current_all_phrases_analysis_list.append({
                    "phrase": phrase,
                    "global_count": count,
                    "global_probability_percent": global_probability_percent,
                    "source_details": sorted(s_details, key=lambda x: x['count_in_source'], reverse=True)
                })
            current_all_phrases_analysis_list_sorted = sorted(current_all_phrases_analysis_list, key=lambda x: x['global_count'], reverse=True)

            # --- Descriptive Statistics Calculation ---
            current_global_freq_stats = calculate_descriptive_stats(all_frequencies_from_items)
            current_global_perc_stats = calculate_descriptive_stats(all_percentages_from_items)
            current_per_source_stats = {}
            unique_sources = set(per_source_frequencies_map.keys()).union(set(per_source_percentages_map.keys()))
            for src in unique_sources:
                current_per_source_stats[src] = {
                    "frequency_stats": calculate_descriptive_stats(per_source_frequencies_map.get(src, [])),
                    "percentage_stats": calculate_descriptive_stats(per_source_percentages_map.get(src, []))
                }

        except requests.exceptions.HTTPError as e: return error_response(f"Error from transformation API: {e.response.status_code}", status.HTTP_502_BAD_GATEWAY)
        except requests.exceptions.RequestException as e: return error_response(f"Failed to contact transformation API: {str(e)}", status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e: return error_response(f"Error during initial data processing: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Inferential Statistics & Probabilistic Forecasting ---
        inferential_summary = {"comparison_target": "No previous analysis found."}
        probabilistic_forecast = {"notes": "Insufficient historical data for trend analysis or forecasting."}

        # Fetch NUM_PREVIOUS_RUNS_FOR_TREND records efficiently
        recent_analyses_qs = list(VisualizationData.objects.order_by('-createdAt').values(
            'global_frequency_stats', 'all_phrases_analysis', 'createdAt'
        )[:self.NUM_PREVIOUS_RUNS_FOR_TREND])

        previous_analysis_raw = recent_analyses_qs[0] if recent_analyses_qs else None

        if previous_analysis_raw:
            inferential_summary["comparison_target"] = f"Previous analysis created At: {previous_analysis_raw['createdAt'].isoformat()}"

            prev_freq_stats = previous_analysis_raw['global_frequency_stats']
            # T-test for mean frequency
            if current_global_freq_stats["count"] > 1 and prev_freq_stats.get("count", 0) > 1 and \
               current_global_freq_stats.get("std_dev") is not None and prev_freq_stats.get("std_dev") is not None and \
               current_global_freq_stats["std_dev"] >= 0 and prev_freq_stats["std_dev"] >= 0: # std_dev can be 0 for constant data
                try:
                    t_stat_freq, p_val_freq = scipy_stats.ttest_ind_from_stats(
                        mean1=current_global_freq_stats["mean"], std1=current_global_freq_stats["std_dev"], nobs1=current_global_freq_stats["count"],
                        mean2=prev_freq_stats["mean"], std2=prev_freq_stats["std_dev"], nobs2=prev_freq_stats["count"]
                    )
                    inferential_summary["global_frequency_mean_ttest"] = {
                        "statistic": round(t_stat_freq, 4),
                        "p_value": round(p_val_freq, 4),
                        "interpretation": self._get_interpretation(p_val_freq, test_type="difference in mean frequency")
                    }
                except ValueError: # e.g., if nobs is too small, or std_dev prevents calculation
                     inferential_summary["global_frequency_mean_ttest"] = {"notes": "Could not perform t-test. Data might be constant or insufficient observations."}
            else:
                 inferential_summary["global_frequency_mean_ttest"] = {"notes": "Insufficient data (count <= 1 or std_dev is None) for t-test."}

            # F-test for variance frequency
            if current_global_freq_stats.get("variance") is not None and prev_freq_stats.get("variance") is not None and \
               current_global_freq_stats["count"] > 1 and prev_freq_stats["count"] > 1: # Variances can be 0
                try:
                    f_stat_var = current_global_freq_stats["variance"] / prev_freq_stats["variance"] if prev_freq_stats["variance"] > 0 else np.inf # Handle division by zero for F-stat
                    p_val_var = scipy_stats.f.sf(f_stat_var, current_global_freq_stats["count"] - 1, prev_freq_stats["count"] - 1)
                    inferential_summary["global_frequency_variance_ftest"] = {
                        "statistic": round(f_stat_var, 4),
                        "p_value": round(p_val_var, 4),
                        "interpretation": self._get_interpretation(p_val_var, test_type="difference in frequency variance")
                    }
                except (ValueError, ZeroDivisionError): # e.g., if dof is too small, or variance is zero for both
                    inferential_summary["global_frequency_variance_ftest"] = {"notes": "Could not perform F-test. Data might be constant or insufficient observations."}
            else:
                inferential_summary["global_frequency_variance_ftest"] = {"notes": "Insufficient data (count <= 1 or variance is None) for F-test."}

            # Chi-square test for phrase distribution
            current_top_phrases_dict = {p['phrase']: p['global_count'] for p in current_all_phrases_analysis_list_sorted[:20]}
            prev_top_phrases_dict = {p['phrase']: p['global_count'] for p in previous_analysis_raw['all_phrases_analysis'][:20]}
            common_phrases = sorted(list(set(current_top_phrases_dict.keys()).intersection(set(prev_top_phrases_dict.keys()))))

            if len(common_phrases) >= 2: # At least 2 common phrases for chi-square
                observed_counts_current = [current_top_phrases_dict.get(p, 0) for p in common_phrases]
                observed_counts_previous = [prev_top_phrases_dict.get(p, 0) for p in common_phrases]
                
                # Filter out columns where both observed counts are zero
                filtered_current = []
                filtered_previous = []
                for cur, prev in zip(observed_counts_current, observed_counts_previous):
                    if cur > 0 or prev > 0:
                        filtered_current.append(cur)
                        filtered_previous.append(prev)
                
                if len(filtered_current) >= 2: # Need at least 2 non-zero columns
                    contingency_table = [filtered_current, filtered_previous]
                    try:
                        chi2_stat, p_val_chi2, dof, expected = scipy_stats.chi2_contingency(contingency_table)
                        inferential_summary["phrase_distribution_chi2test"] = {
                            "statistic": round(chi2_stat,4),
                            "p_value": round(p_val_chi2,4),
                            "dof": dof,
                            "interpretation": self._get_interpretation(p_val_chi2, test_type="difference in phrase distributions (top common phrases)")
                        }
                    except ValueError:
                        inferential_summary["phrase_distribution_chi2test"] = {"notes": "Could not perform Chi-square test due to data structure (e.g., too few common phrases or zero counts after filtering)."}
                else:
                    inferential_summary["phrase_distribution_chi2test"] = {"notes": "Not enough non-zero common top phrases for Chi-square test."}
            else:
                inferential_summary["phrase_distribution_chi2test"] = {"notes": "Not enough common top phrases between current and previous run for Chi-square test."}

            # --- Probabilistic Forecasting (Trend Analysis) ---
            # Re-fetch recent analyses to get means for the trend calculation, including the current one if applicable
            all_means_for_trend = [
                float(rec['global_frequency_stats'].get('mean', 0))
                for rec in reversed(recent_analyses_qs) # Reversed to get chronological order
                if rec['global_frequency_stats'].get('mean') is not None
            ]
            if current_global_freq_stats.get('mean') is not None:
                all_means_for_trend.append(float(current_global_freq_stats['mean']))


            if len(all_means_for_trend) >= 2:
                indices = np.arange(len(all_means_for_trend))
                # Filter out NaNs if any means are None (shouldn't happen with current calculate_descriptive_stats)
                valid_indices = [i for i, val in enumerate(all_means_for_trend) if val is not None]
                if len(valid_indices) >= 2:
                    filtered_means = [all_means_for_trend[i] for i in valid_indices]
                    filtered_indices = [indices[i] for i in valid_indices]

                    slope, intercept, r_value, p_value_regr, std_err = scipy_stats.linregress(filtered_indices, filtered_means)

                    direction = "stable"
                    if slope > 0.001: direction = "increasing" # Small threshold for significant change
                    elif slope < -0.001: direction = "decreasing"

                    next_index = len(all_means_for_trend) # The index for the next period
                    predicted_next_mean_freq = intercept + slope * next_index

                    probabilistic_forecast["mean_frequency_trend"] = {
                        "slope": round(slope, 4),
                        "intercept": round(intercept, 4),
                        "r_squared": round(r_value**2, 4),
                        "p_value_for_slope": round(p_value_regr, 4),
                        "direction": direction,
                        "next_period_prediction": round(predicted_next_mean_freq, 4),
                        "interpretation": self._get_interpretation(p_value_regr, test_type="significance of trend")
                    }

                    changes = np.diff(np.array(all_means_for_trend))
                    if len(changes) > 0:
                        probabilistic_forecast["prob_freq_increase_empiric_pct"] = round((Decimal(np.sum(changes > 0)) / Decimal(len(changes))) * Decimal(100), 2)
                        probabilistic_forecast["prob_freq_decrease_empiric_pct"] = round((Decimal(np.sum(changes < 0)) / Decimal(len(changes))) * Decimal(100), 2)
                else:
                    probabilistic_forecast["mean_frequency_trend"] = {"notes": "Not enough valid data points for trend analysis after filtering NaNs."}
            else:
                probabilistic_forecast["mean_frequency_trend"] = {"notes": "Not enough data points for trend analysis."}


        try:
            with transaction.atomic():
                analysis_result_obj = VisualizationData.objects.create(
                    analyzed_endpoint=source_data_url,
                    # input_transformed_data=all_transformed_items, # Consider if really needed or if summary is enough
                    all_phrases_analysis=current_all_phrases_analysis_list_sorted,
                    global_frequency_stats=current_global_freq_stats,
                    global_percentage_stats=current_global_perc_stats,
                    per_source_stats=current_per_source_stats,
                    probabilistic_insights=probabilistic_forecast,
                    inferential_stats_summary=inferential_summary
                )

            serializer = VisualizationDataSerializer(analysis_result_obj)
            return success_response(
                data=serializer.data,
                message=f"Advanced analysis complete. Insights from {len(all_transformed_items)} items stored, compared with previous run.",
                code=status.HTTP_201_CREATED
            )
        except Exception as e:
            return error_response(message=f"Error saving analysis results: {str(e)}", code=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @extend_schema(
        summary="Retrieve stored visualization analysis",
        description="Fetches and returns a list of all stored analysis results with pagination.",
        tags=["Data Visualization & Analysis"],
        parameters=[
            OpenApiParameter(name='page', type=OpenApiTypes.INT, description='Page number to retrieve.', default=1),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, description='Number of items per page.', default=50),
        ],
        responses={
            200: OpenApiResponse(description="Analysis results fetched successfully.", response=ListVisualizationDataResponseWrapperSerializer),
            500: OpenApiResponse(description="Internal server error.", response=VisualizationErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_analysis_results(self, request):
        try:
            queryset = VisualizationData.objects.all().order_by('-createdAt')
            
            paginator = CustomVisualizationPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            serializer = VisualizationDataSerializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return error_response(message=f"Failed to fetch analysis results: {str(e)}", data=[], code=status.HTTP_500_INTERNAL_SERVER_ERROR)