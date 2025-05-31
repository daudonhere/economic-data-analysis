from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock
import requests # For mocking exceptions
from decimal import Decimal

from visualizationApp.models import VisualizationData
from visualizationApp.serializers import VisualizationDataSerializer
# Assuming AnalysisService is in visualizationApp.services
from visualizationApp.services import AnalysisService
from configs.endpoint import SERVICES_VISUALIZATION_PATH # This is the transformationApp collect URL

class TestVisualizationViewSetList(TestCase):
    def setUp(self):
        self.client = Client()
        self.data1 = VisualizationData.objects.create(
            analyzed_endpoint="http://example.com/transform/source1",
            input_transformed_data=[{"text": "data1"}],
            all_phrases_analysis=[{"phrase": "data1", "global_count": 1}],
            global_frequency_stats={"mean": 1.0, "count": 1},
            global_percentage_stats={"mean": 0.5, "count": 1},
            per_source_stats={},
            probabilistic_insights={},
            inferential_stats_summary={}
        )
        self.collect_url = "/visualization/collect/"

    def test_list_visualization_data(self):
        response = self.client.get(self.collect_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        self.assertEqual(response_data.get("status"), "success")
        self.assertEqual(response_data.get("code"), status.HTTP_200_OK)
        self.assertIn("Data fetched successfully.", response_data.get("messages", ""))

        self.assertEqual(len(response_data["data"]), 1)
        self.assertEqual(response_data["data"][0]["analyzed_endpoint"], self.data1.analyzed_endpoint)


class TestVisualizationAnalyzeAction(TestCase):
    def setUp(self):
        self.client = Client()
        self.analyze_url = "/visualization/analyze/"
        self.mock_transformation_api_url = f"http://testserver{SERVICES_VISUALIZATION_PATH}"

    @patch('visualizationApp.views.requests.get')
    @patch('visualizationApp.services.AnalysisService.run_analysis') # Patch within services module
    def test_successful_analysis(self, mock_run_analysis, mock_requests_get_transform):
        # Mock response from transformation service
        mock_transform_response = MagicMock()
        mock_transform_response.status_code = 200
        mock_transform_data = [
            {"source": "s1", "content": {"text": "apple banana"}, "frequency": "1.0", "percentage": "0.0"}
        ]
        mock_transform_response.json.return_value = {"data": mock_transform_data}
        mock_requests_get_transform.return_value = mock_transform_response

        # Mock return value of AnalysisService.run_analysis
        mock_analysis_results = {
            "all_phrases_analysis": [{"phrase": "apple", "global_count": 1}],
            "global_frequency_stats": {"mean": 1.0, "count": 1},
            "global_percentage_stats": {"mean": 0.0, "count": 1},
            "per_source_stats": {"s1": {"frequency_stats": {"mean": 1.0}}},
            "probabilistic_insights": {"notes": "test forecast"},
            "inferential_stats_summary": {"notes": "test summary"}
        }
        mock_run_analysis.return_value = mock_analysis_results

        response = self.client.post(self.analyze_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("Advanced analysis complete", response_data["messages"])

        self.assertEqual(VisualizationData.objects.count(), 1)
        created_viz = VisualizationData.objects.first()
        self.assertEqual(created_viz.analyzed_endpoint, self.mock_transformation_api_url)
        self.assertEqual(created_viz.input_transformed_data, mock_transform_data)
        self.assertEqual(created_viz.all_phrases_analysis, mock_analysis_results["all_phrases_analysis"])
        # ... (check other fields from mock_analysis_results)
        mock_run_analysis.assert_called_once()


    @patch('visualizationApp.views.requests.get')
    def test_no_data_from_transformation_api(self, mock_requests_get_transform):
        mock_transform_response = MagicMock()
        mock_transform_response.status_code = 200
        mock_transform_response.json.return_value = {"data": []} # Empty list
        mock_requests_get_transform.return_value = mock_transform_response

        response = self.client.post(self.analyze_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK) # As per view logic
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("No data from transformation API. Empty analysis record created.", response_data["messages"])

        self.assertEqual(VisualizationData.objects.count(), 1)
        created_viz = VisualizationData.objects.first()
        self.assertEqual(created_viz.input_transformed_data, [])
        self.assertEqual(created_viz.all_phrases_analysis, [])
        # Check that stats are empty/default as per view logic for this case
        self.assertEqual(created_viz.global_frequency_stats["count"], 0)


    @patch('visualizationApp.views.requests.get')
    def test_error_from_transformation_data_api(self, mock_requests_get_transform):
        mock_transform_response = MagicMock()
        mock_transform_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Transform API Error")
        mock_transform_response.status_code = 502
        # mock_transform_response.text = "Transform API is down" # views.py doesn't use .text for this error
        mock_requests_get_transform.return_value = mock_transform_response

        response = self.client.post(self.analyze_url)
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        # The exact message format might vary, check for key parts
        self.assertIn("Error from transformation API", response_data["messages"])
        self.assertEqual(VisualizationData.objects.count(), 0)

    @patch('visualizationApp.views.requests.get')
    def test_unexpected_structure_from_transformation_api(self, mock_requests_get_transform):
        mock_transform_response = MagicMock()
        mock_transform_response.status_code = 200
        # This structure will cause an error in the view when trying to access response_json.get("data", [])
        mock_transform_response.json.return_value = {"unexpected_format": "no data key"}
        mock_requests_get_transform.return_value = mock_transform_response

        response = self.client.post(self.analyze_url)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        # This error is caught by the generic Exception handler in analyze_and_store_insights_advanced
        self.assertIn("Error saving analysis results", response_data["messages"])
        self.assertEqual(VisualizationData.objects.count(), 0)

    @patch('visualizationApp.views.requests.get')
    @patch('visualizationApp.services.AnalysisService.run_analysis')
    def test_analysis_service_exception(self, mock_run_analysis, mock_requests_get_transform):
        # Mock successful fetch from transformation API
        mock_transform_response = MagicMock()
        mock_transform_response.status_code = 200
        mock_transform_data = [{"source": "s1", "content": {"text": "some data"}}]
        mock_transform_response.json.return_value = {"data": mock_transform_data}
        mock_requests_get_transform.return_value = mock_transform_response

        # Mock AnalysisService.run_analysis to raise an exception
        mock_run_analysis.side_effect = Exception("Internal AnalysisService error")

        response = self.client.post(self.analyze_url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        # This error is caught by the generic Exception handler in analyze_and_store_insights_advanced
        self.assertIn("Error saving analysis results: Internal AnalysisService error", response_data["messages"])
        self.assertEqual(VisualizationData.objects.count(), 0)
