from decimal import Decimal
from collections import Counter, defaultdict
import numpy as np
from scipy import stats as scipy_stats # Corrected import for scipy.stats
from typing import List, Dict, Any, Union, Optional # For type hinting

from common.utils import extract_all_strings_from_json, calculate_descriptive_stats
from visualizationApp.models import VisualizationData # Assuming this is the correct model path

class AnalysisService:
    def __init__(self,
                 transformed_items_list: List[Dict[str, Any]],
                 previous_analysis_qs_for_trend: List[VisualizationData],
                 previous_analysis_for_comparison: Optional[VisualizationData]):

        self.transformed_items_list: List[Dict[str, Any]] = transformed_items_list
        self.previous_analysis_qs_for_trend: List[VisualizationData] = previous_analysis_qs_for_trend
        self.previous_analysis_for_comparison: Optional[VisualizationData] = previous_analysis_for_comparison

        # Initialize attributes for storing results
        self.current_all_phrases_analysis_list_sorted: List[Dict[str, Any]] = []
        self.current_global_freq_stats: Dict[str, Any] = {}
        self.current_global_perc_stats: Dict[str, Any] = {}
        self.current_per_source_stats: Dict[str, Any] = {}
        self.inferential_summary: Dict[str, Any] = {"comparison_target": "No previous analysis found."}
        self.probabilistic_forecast: Dict[str, Any] = {"notes": "Insufficient historical data for trend analysis or forecasting."}
        self.NUM_PREVIOUS_RUNS_FOR_TREND = 5 # Matching the ViewSet's constant

    def _perform_phrase_analysis(self):
        all_extracted_phrases_from_all_items: List[str] = []
        source_phrase_details: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"phrases_counter": Counter(), "total_phrases_in_source": 0})

        for item in self.transformed_items_list:
            content_json = item.get('content')
            source_url = item.get('source')

            phrases = extract_all_strings_from_json(content_json if content_json else {}) # Handle None content
            all_extracted_phrases_from_all_items.extend(phrases)
            if source_url:
                source_phrase_details[source_url]["phrases_counter"].update(phrases)
                source_phrase_details[source_url]["total_phrases_in_source"] += len(phrases)

        global_phrase_counts = Counter(all_extracted_phrases_from_all_items)
        current_all_phrases_analysis_list: List[Dict[str, Any]] = []
        total_phrases_overall_count = sum(global_phrase_counts.values())

        for phrase, count in global_phrase_counts.items():
            s_details: List[Dict[str, Any]] = []
            for src, details in source_phrase_details.items():
                c_in_s = details["phrases_counter"].get(phrase, 0)
                if c_in_s > 0:
                    percentage = round((c_in_s / details["total_phrases_in_source"]) * 100, 2) if details["total_phrases_in_source"] > 0 else 0
                    s_details.append({
                        "source_url": src,
                        "count_in_source": c_in_s,
                        "percentage_in_source": percentage
                    })

            global_prob_percent = round((count / total_phrases_overall_count) * 100, 2) if total_phrases_overall_count > 0 else 0
            current_all_phrases_analysis_list.append({
                "phrase": phrase,
                "global_count": count,
                "global_probability_percent": global_prob_percent,
                "source_details": sorted(s_details, key=lambda x: x['count_in_source'], reverse=True)
            })

        self.current_all_phrases_analysis_list_sorted = sorted(current_all_phrases_analysis_list, key=lambda x: x['global_count'], reverse=True)

    def _calculate_global_and_source_stats(self):
        all_frequencies_from_items: List[Decimal] = []
        all_percentages_from_items: List[Decimal] = []
        per_source_frequencies_map: Dict[str, List[Decimal]] = defaultdict(list)
        per_source_percentages_map: Dict[str, List[Decimal]] = defaultdict(list)

        for item in self.transformed_items_list:
            source_url = item.get('source')
            item_freq = item.get('frequency')
            item_perc = item.get('percentage')

            if item_freq is not None:
                try:
                    val = Decimal(str(item_freq))
                    all_frequencies_from_items.append(val)
                    if source_url: per_source_frequencies_map[source_url].append(val)
                except: pass # Ignore conversion errors
            if item_perc is not None:
                try:
                    val = Decimal(str(item_perc))
                    all_percentages_from_items.append(val)
                    if source_url: per_source_percentages_map[source_url].append(val)
                except: pass # Ignore conversion errors

        self.current_global_freq_stats = calculate_descriptive_stats(all_frequencies_from_items)
        self.current_global_perc_stats = calculate_descriptive_stats(all_percentages_from_items)

        current_per_source_stats_temp: Dict[str, Dict[str, Any]] = {}
        unique_sources = set(per_source_frequencies_map.keys()).union(set(per_source_percentages_map.keys()))
        for src in unique_sources:
            current_per_source_stats_temp[src] = {
                "frequency_stats": calculate_descriptive_stats(per_source_frequencies_map.get(src, [])),
                "percentage_stats": calculate_descriptive_stats(per_source_percentages_map.get(src, []))
            }
        self.current_per_source_stats = current_per_source_stats_temp

    def _get_interpretation(self, p_value: Optional[float], alpha: float = 0.05, test_type: str = "general") -> str:
        if p_value is None:
            return "Test not performed or not applicable."
        if p_value < alpha:
            return f"Significant result (p < {alpha}): Indicates a statistically significant {test_type}."
        else:
            return f"Not significant (p >= {alpha}): No statistically significant {test_type} detected."

    def _perform_inferential_statistics(self):
        if not self.previous_analysis_for_comparison:
            return # No previous analysis to compare against

        self.inferential_summary["comparison_target"] = f"Previous analysis ID: {self.previous_analysis_for_comparison.id}, Created At: {self.previous_analysis_for_comparison.createdAt.isoformat()}"

        prev_freq_stats = self.previous_analysis_for_comparison.global_frequency_stats or {}

        # Ensure all necessary keys exist for t-test and F-test
        current_mean = self.current_global_freq_stats.get("mean")
        current_std_dev = self.current_global_freq_stats.get("std_dev")
        current_count = self.current_global_freq_stats.get("count", 0)
        prev_mean = prev_freq_stats.get("mean")
        prev_std_dev = prev_freq_stats.get("std_dev")
        prev_count = prev_freq_stats.get("count", 0)

        if current_count > 1 and prev_count > 1 and \
           current_mean is not None and current_std_dev is not None and current_std_dev > 0 and \
           prev_mean is not None and prev_std_dev is not None and prev_std_dev > 0:
            t_stat_freq, p_val_freq = scipy_stats.ttest_ind_from_stats(
                mean1=current_mean, std1=current_std_dev, nobs1=current_count,
                mean2=prev_mean, std2=prev_std_dev, nobs2=prev_count
            )
            self.inferential_summary["global_frequency_mean_ttest"] = {"statistic": round(t_stat_freq, 4), "p_value": round(p_val_freq, 4), "interpretation": self._get_interpretation(p_val_freq, test_type="difference in mean frequency")}
        else:
            self.inferential_summary["global_frequency_mean_ttest"] = {"notes": "Insufficient data (std_dev is 0 or None, or count <=1) for t-test."}

        current_variance = self.current_global_freq_stats.get("variance")
        prev_variance = prev_freq_stats.get("variance")
        if current_variance is not None and prev_variance is not None and \
           current_variance > 0 and prev_variance > 0 and \
           current_count > 1 and prev_count > 1:
            f_stat_var = current_variance / prev_variance
            p_val_var = scipy_stats.f.sf(f_stat_var, current_count - 1, prev_count - 1)
            self.inferential_summary["global_frequency_variance_ftest"] = {"statistic": round(f_stat_var, 4), "p_value": round(p_val_var, 4), "interpretation": self._get_interpretation(p_val_var, test_type="difference in frequency variance")}
        else:
            self.inferential_summary["global_frequency_variance_ftest"] = {"notes": "Insufficient data (variance is 0 or None, or count <= 1) for F-test."}

        current_top_phrases_dict = {p['phrase']: p['global_count'] for p in self.current_all_phrases_analysis_list_sorted[:20]}
        prev_top_phrases_dict = {p['phrase']: p['global_count'] for p in (self.previous_analysis_for_comparison.all_phrases_analysis or [])[:20]}
        common_phrases = set(current_top_phrases_dict.keys()).intersection(set(prev_top_phrases_dict.keys()))

        if len(common_phrases) >= 2:
            observed_counts_current = [current_top_phrases_dict[p] for p in common_phrases]
            observed_counts_previous = [prev_top_phrases_dict[p] for p in common_phrases]
            # Ensure no zero counts if chi2_contingency requires it (depends on scipy version behavior)
            if all(c > 0 for c in observed_counts_current) and all(c > 0 for c in observed_counts_previous):
                contingency_table = [observed_counts_current, observed_counts_previous]
                try:
                    chi2_stat, p_val_chi2, dof, expected = scipy_stats.chi2_contingency(contingency_table)
                    self.inferential_summary["phrase_distribution_chi2test"] = {"statistic": round(chi2_stat,4), "p_value": round(p_val_chi2,4), "dof": dof, "interpretation": self._get_interpretation(p_val_chi2, test_type="difference in phrase distributions (top common phrases)")}
                except ValueError: # Catch errors from chi2_contingency
                    self.inferential_summary["phrase_distribution_chi2test"] = {"notes": "Could not perform Chi-square test due to data structure (e.g., sum of frequencies is zero)."}
            else:
                self.inferential_summary["phrase_distribution_chi2test"] = {"notes": "Skipped Chi-square test due to zero counts in common phrases."}

        else:
            self.inferential_summary["phrase_distribution_chi2test"] = {"notes": "Not enough common top phrases (need at least 2) for Chi-square test."}

    def _perform_probabilistic_forecasting(self):
        # Extract historical mean frequencies, ensuring they are float and not None
        historical_mean_freqs: List[float] = []
        for ra in reversed(self.previous_analysis_qs_for_trend): # Reversed to have oldest first
            if ra.global_frequency_stats and ra.global_frequency_stats.get("mean") is not None:
                try:
                    historical_mean_freqs.append(float(ra.global_frequency_stats["mean"]))
                except (ValueError, TypeError):
                    pass # Skip if conversion fails

        current_mean_freq_for_trend: Optional[float] = None
        if self.current_global_freq_stats.get("mean") is not None:
            try:
                current_mean_freq_for_trend = float(self.current_global_freq_stats["mean"])
            except (ValueError, TypeError):
                pass

        all_means_for_trend = historical_mean_freqs
        if current_mean_freq_for_trend is not None:
            all_means_for_trend.append(current_mean_freq_for_trend)

        # Ensure we have enough data points for regression
        if len(all_means_for_trend) >= 2: # Need at least 2 points for linregress
            indices = np.arange(len(all_means_for_trend))
            try:
                slope, intercept, r_value, p_value_regr, std_err = scipy_stats.linregress(indices, all_means_for_trend)

                direction = "stable"
                if slope > 0.01: direction = "increasing"
                elif slope < -0.01: direction = "decreasing"

                next_index = len(all_means_for_trend) # Predict for the next period
                predicted_next_mean_freq = intercept + slope * next_index

                self.probabilistic_forecast["mean_frequency_trend"] = {
                    "slope": round(slope, 4), "intercept": round(intercept, 4),
                    "r_squared": round(r_value**2, 4), "p_value_for_slope": round(p_value_regr, 4),
                    "direction": direction, "next_period_prediction": round(predicted_next_mean_freq, 4),
                    "interpretation": self._get_interpretation(p_value_regr, test_type="significance of trend")
                }

                changes = np.diff(all_means_for_trend)
                if len(changes) > 0: # Need at least one change
                    self.probabilistic_forecast["prob_freq_increase_empiric_pct"] = round((np.sum(changes > 0) / len(changes)) * 100, 2)
                    self.probabilistic_forecast["prob_freq_decrease_empiric_pct"] = round((np.sum(changes < 0) / len(changes)) * 100, 2)
            except ValueError as e: # Catch potential errors from linregress
                 self.probabilistic_forecast["mean_frequency_trend"] = {"notes": f"Linear regression failed: {e}"}
        else:
            # Not enough data points, keep default note
            pass


    def run_analysis(self) -> Dict[str, Any]:
        self._perform_phrase_analysis()
        self._calculate_global_and_source_stats()
        self._perform_inferential_statistics()
        self._perform_probabilistic_forecasting()

        return {
            "all_phrases_analysis": self.current_all_phrases_analysis_list_sorted,
            "global_frequency_stats": self.current_global_freq_stats,
            "global_percentage_stats": self.current_global_perc_stats,
            "per_source_stats": self.current_per_source_stats,
            "probabilistic_insights": self.probabilistic_forecast,
            "inferential_stats_summary": self.inferential_summary
        }
