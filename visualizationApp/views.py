import requests
from decimal import Decimal, ROUND_HALF_UP
from collections import Counter, defaultdict
import numpy as np
from scipy import stats as scipy_stats
from django.db import transaction
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response 
from visualizationApp.models import VisualizationData
from visualizationApp.serializers import VisualizationDataSerializer
from configs.endpoint import SERVICES_VISUALIZATION_PATH

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
    
    valid_data = [float(x) for x in data_list if x is not None and isinstance(x, (int, float, Decimal))]
    if not valid_data:
        return {"mean": None, "median": None, "std_dev": None, "variance": None, "count": 0, "min": None, "max": None, "sum": None}

    arr = np.array(valid_data, dtype=float)
    return {
        "mean": round(np.mean(arr), 4) if arr.size > 0 else None,
        "median": round(np.median(arr), 4) if arr.size > 0 else None,
        "std_dev": round(np.std(arr), 4) if arr.size > 0 else None,
        "variance": round(np.var(arr), 4) if arr.size > 0 else None,
        "count": len(valid_data),
        "min": round(np.min(arr), 4) if arr.size > 0 else None,
        "max": round(np.max(arr), 4) if arr.size > 0 else None,
        "sum": round(np.sum(arr), 4) if arr.size > 0 else None,
    }

class VisualizationAnalysisViewSet(viewsets.ViewSet):
    serializer_class = VisualizationDataSerializer
    NUM_PREVIOUS_RUNS_FOR_TREND = 5

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
            response = requests.get(source_data_url, timeout=20)
            response.raise_for_status()
            response_json = response.json()
            transformed_items_list = response_json.get("data", [])
            
            if not isinstance(transformed_items_list, list):
                 return error_response(message="Unexpected data structure from transformation data API.", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if not transformed_items_list:
                with transaction.atomic():
                    analysis_obj = VisualizationData.objects.create(
                        analyzed_endpoint=source_data_url, input_transformed_data=[],
                        all_phrases_analysis=[], global_frequency_stats=calculate_descriptive_stats([]),
                        global_percentage_stats=calculate_descriptive_stats([]), per_source_stats={},
                        probabilistic_insights={"notes": "No source data to process for advanced probability."},
                        inferential_stats_summary={"notes": "No source data for comparison or inferential tests."}
                    )
                return success_response(data=VisualizationDataSerializer(analysis_obj).data, message="No data from transformation API. Empty analysis record created.", code=status.HTTP_200_OK)

            all_extracted_phrases_from_all_items = []
            source_phrase_details = defaultdict(lambda: {"phrases_counter": Counter(), "total_phrases_in_source": 0})
            all_frequencies_from_items = []
            all_percentages_from_items = []
            per_source_frequencies_map = defaultdict(list)
            per_source_percentages_map = defaultdict(list)

            for item in transformed_items_list:
                content_json, source_url = item.get('content'), item.get('source')
                item_freq, item_perc = item.get('frequency'), item.get('percentage')
                if item_freq is not None:
                    try: 
                        val = Decimal(str(item_freq))
                        all_frequencies_from_items.append(val)
                        if source_url: per_source_frequencies_map[source_url].append(val)
                    except: pass
                if item_perc is not None:
                    try:
                        val = Decimal(str(item_perc))
                        all_percentages_from_items.append(val)
                        if source_url: per_source_percentages_map[source_url].append(val)
                    except: pass
                phrases = extract_all_strings_from_json(content_json)
                all_extracted_phrases_from_all_items.extend(phrases)
                if source_url:
                    source_phrase_details[source_url]["phrases_counter"].update(phrases)
                    source_phrase_details[source_url]["total_phrases_in_source"] += len(phrases)
            
            global_phrase_counts = Counter(all_extracted_phrases_from_all_items)
            current_all_phrases_analysis_list = []
            total_phrases_overall_count = sum(global_phrase_counts.values())
            for phrase, count in global_phrase_counts.items():
                s_details = []
                for src, details in source_phrase_details.items():
                    c_in_s = details["phrases_counter"].get(phrase,0)
                    if c_in_s > 0: s_details.append({"source_url": src, "count_in_source": c_in_s, "percentage_in_source": round((c_in_s / details["total_phrases_in_source"]) * 100, 2) if details["total_phrases_in_source"] > 0 else 0})
                current_all_phrases_analysis_list.append({"phrase": phrase, "global_count": count, "global_probability_percent": round((count / total_phrases_overall_count) * 100, 2) if total_phrases_overall_count > 0 else 0, "source_details": sorted(s_details, key=lambda x: x['count_in_source'], reverse=True)})
            current_all_phrases_analysis_list_sorted = sorted(current_all_phrases_analysis_list, key=lambda x: x['global_count'], reverse=True)
            
            current_global_freq_stats = calculate_descriptive_stats(all_frequencies_from_items)
            current_global_perc_stats = calculate_descriptive_stats(all_percentages_from_items)
            current_per_source_stats = {}
            unique_sources = set(per_source_frequencies_map.keys()).union(set(per_source_percentages_map.keys()))
            for src in unique_sources:
                current_per_source_stats[src] = {"frequency_stats": calculate_descriptive_stats(per_source_frequencies_map.get(src,[])), "percentage_stats": calculate_descriptive_stats(per_source_percentages_map.get(src,[]))}

        except requests.exceptions.HTTPError as e: return error_response(f"Error from transformation API: {e.response.status_code}", status.HTTP_502_BAD_GATEWAY)
        except requests.exceptions.RequestException as e: return error_response(f"Failed to contact transformation API: {str(e)}", status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e: return error_response(f"Error during initial data processing: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

        inferential_summary = {"comparison_target": "No previous analysis found."}
        probabilistic_forecast = {"notes": "Insufficient historical data for trend analysis or forecasting."}
        
        previous_analysis = VisualizationData.objects.order_by('-createdAt').first()

        if previous_analysis:
            inferential_summary["comparison_target"] = f"Previous analysis ID: {previous_analysis.id}, Created At: {previous_analysis.createdAt.isoformat()}"
            
            prev_freq_stats = previous_analysis.global_frequency_stats
            if current_global_freq_stats["count"] > 1 and prev_freq_stats.get("count", 0) > 1:
                if current_global_freq_stats.get("std_dev") is not None and prev_freq_stats.get("std_dev") is not None and current_global_freq_stats["std_dev"] > 0 and prev_freq_stats["std_dev"] > 0 :
                    t_stat_freq, p_val_freq = scipy_stats.ttest_ind_from_stats(
                        mean1=current_global_freq_stats["mean"], std1=current_global_freq_stats["std_dev"], nobs1=current_global_freq_stats["count"],
                        mean2=prev_freq_stats["mean"], std2=prev_freq_stats["std_dev"], nobs2=prev_freq_stats["count"]
                    )
                    inferential_summary["global_frequency_mean_ttest"] = {"statistic": round(t_stat_freq, 4), "p_value": round(p_val_freq, 4), "interpretation": self._get_interpretation(p_val_freq, test_type="difference in mean frequency")}
                else:
                     inferential_summary["global_frequency_mean_ttest"] = {"notes": "Insufficient data (std_dev is 0 or None) for t-test."}

            if current_global_freq_stats.get("variance") is not None and prev_freq_stats.get("variance") is not None and \
               current_global_freq_stats["variance"] > 0 and prev_freq_stats["variance"] > 0 and \
               current_global_freq_stats["count"] > 1 and prev_freq_stats["count"] > 1:
                f_stat_var = current_global_freq_stats["variance"] / prev_freq_stats["variance"]
                p_val_var = scipy_stats.f.sf(f_stat_var, current_global_freq_stats["count"]-1, prev_freq_stats["count"]-1)
                inferential_summary["global_frequency_variance_ftest"] = {"statistic": round(f_stat_var, 4), "p_value": round(p_val_var, 4), "interpretation": self._get_interpretation(p_val_var, test_type="difference in frequency variance")}
            else:
                inferential_summary["global_frequency_variance_ftest"] = {"notes": "Insufficient data (variance is 0 or None) for F-test."}

            current_top_phrases_dict = {p['phrase']: p['global_count'] for p in current_all_phrases_analysis_list_sorted[:20]}
            prev_top_phrases_dict = {p['phrase']: p['global_count'] for p in previous_analysis.all_phrases_analysis[:20]}
            common_phrases = set(current_top_phrases_dict.keys()).intersection(set(prev_top_phrases_dict.keys()))
            
            if len(common_phrases) >= 2:
                observed_counts_current = [current_top_phrases_dict[p] for p in common_phrases]
                observed_counts_previous = [prev_top_phrases_dict[p] for p in common_phrases]
                contingency_table = [observed_counts_current, observed_counts_previous]
                try:
                    chi2_stat, p_val_chi2, dof, expected = scipy_stats.chi2_contingency(contingency_table)
                    inferential_summary["phrase_distribution_chi2test"] = {"statistic": round(chi2_stat,4), "p_value": round(p_val_chi2,4), "dof": dof, "interpretation": self._get_interpretation(p_val_chi2, test_type="difference in phrase distributions (top common phrases)")}
                except ValueError:
                    inferential_summary["phrase_distribution_chi2test"] = {"notes": "Could not perform Chi-square test due to data structure (e.g., too few common phrases or zero counts)."}

            else:
                inferential_summary["phrase_distribution_chi2test"] = {"notes": "Not enough common top phrases between current and previous run for Chi-square test."}
            recent_analyses_qs = VisualizationData.objects.order_by('-createdAt')[:self.NUM_PREVIOUS_RUNS_FOR_TREND-1]
            historical_mean_freqs = [float(ra.global_frequency_stats.get("mean", 0)) for ra in reversed(recent_analyses_qs) if ra.global_frequency_stats.get("mean") is not None]
            if current_global_freq_stats.get("mean") is not None:
                current_mean_freq_for_trend = float(current_global_freq_stats["mean"])
                all_means_for_trend = historical_mean_freqs + [current_mean_freq_for_trend]
            else:
                all_means_for_trend = historical_mean_freqs

            if len(all_means_for_trend) >= 2:
                indices = np.arange(len(all_means_for_trend))
                slope, intercept, r_value, p_value_regr, std_err = scipy_stats.linregress(indices, all_means_for_trend)
                
                direction = "stable"
                if slope > 0.01: direction = "increasing"
                elif slope < -0.01: direction = "decreasing"
                
                next_index = len(all_means_for_trend)
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

                changes = np.diff(all_means_for_trend)
                if len(changes) > 0:
                    probabilistic_forecast["prob_freq_increase_empiric_pct"] = round((np.sum(changes > 0) / len(changes)) * 100, 2)
                    probabilistic_forecast["prob_freq_decrease_empiric_pct"] = round((np.sum(changes < 0) / len(changes)) * 100, 2)
            else:
                probabilistic_forecast["mean_frequency_trend"] = {"notes": "Not enough data points for trend analysis."}
        
        try:
            with transaction.atomic():
                analysis_result_obj = VisualizationData.objects.create(
                    analyzed_endpoint=source_data_url,
                    input_transformed_data=transformed_items_list,
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
            200: OpenApiResponse(description="Analysis results fetched successfully.", response=ListVisualizationDataResponseWrapperSerializer),
            500: OpenApiResponse(description="Internal server error.", response=VisualizationErrorResponseWrapperSerializer)
        }
    )
    @action(detail=False, methods=["get"], url_path="collect")
    def list_analysis_results(self, request):
        try:
            queryset = VisualizationData.objects.all().order_by('-createdAt')
            serializer = VisualizationDataSerializer(queryset, many=True)
            return success_response(data=serializer.data, message="Analysis results fetched successfully.", code=status.HTTP_200_OK)
        except Exception as e:
            return error_response(message=f"Failed to fetch analysis results: {str(e)}", data=[], code=status.HTTP_500_INTERNAL_SERVER_ERROR)