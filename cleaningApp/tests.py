import json
import uuid
import requests # For mocking exceptions
from django.test import TestCase, Client
from django.urls import reverse # For reversing URL names if used, though paths are hardcoded here
from rest_framework import status
from unittest.mock import patch, MagicMock
from cleaningApp.models import CleaningData
from cleaningApp.serializers import GetCleaningDataSerializer
# Assuming SOURCE_SERVICES_URL, SOURCE_SERVICES_TARGET, SOURCE_SERVICES_CLEAN are accessible
# If they are complex to reconstruct or not directly importable for tests, consider mocking them
# or defining simplified versions for testing. For now, assuming they can be imported or are simple enough.
from configs.endpoint import SOURCE_SERVICES_URL, SOURCE_SERVICES_TARGET, SOURCE_SERVICES_CLEAN

class TestCleaningDataViewSetList(TestCase):
    def setUp(self):
        self.client = Client()
        self.data1 = CleaningData.objects.create(
            content={"key": "value1", "cleaned": True},
            source="http://example.com/source1"
        )
        self.data2 = CleaningData.objects.create(
            content={"key": "value2", "other": [1,2,3]},
            source="http://example.com/source2"
        )
        # Note: The /collect endpoint in CleaningDataViewSet uses order_by('-updatedAt')
        # For predictable ordering in tests, ensure updatedAt (or createdAt if used by mixin default) are distinct
        # or control them during creation if precise order is critical for assertions.
        # Here, we'll mostly check for presence and content, so default creation order is often fine.

    def test_list_cleaning_data(self):
        # Assuming the URL is /cleaning/collect/ as per typical DRF ViewSet and ListModelMixin usage
        # If URL structure is different, this needs adjustment.
        response = self.client.get("/cleaning/collect/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        self.assertEqual(response_data.get("status"), "success")
        self.assertEqual(response_data.get("code"), status.HTTP_200_OK)
        self.assertIn("Data fetched successfully", response_data.get("messages", ""))

        # Check that the data contains serialized versions of our objects
        # The order might vary depending on default ordering or explicit ordering in the view
        expected_data = GetCleaningDataSerializer([self.data2, self.data1], many=True).data # Assuming -updatedAt, data2 is newer

        # A more robust check if order is not guaranteed or not important for this test:
        self.assertEqual(len(response_data["data"]), 2)
        response_sources = [item["source"] for item in response_data["data"]]
        self.assertIn(self.data1.source, response_sources)
        self.assertIn(self.data2.source, response_sources)

class TestCleaningDataProcessAction(TestCase):
    def setUp(self):
        self.client = Client()
        self.process_url = "/cleaning/process/" # Assuming this is the correct path

        # Simplified version of SOURCE_SERVICES_CLEAN for testing
        # This avoids direct dependency on the exact content of configs.endpoint if it's complex
        self.test_base_url = "http://testserver" # Django's default test server base
        self.mock_source_services_url = "/mock-ingestion-data/"
        self.mock_target_source_path = "/finance/stock-data/" # Example target
        self.mock_target_source_full_url = f"{self.test_base_url}{self.mock_target_source_path}"

        self.mock_cleaning_rules = {
            self.mock_target_source_path: { # Path relative to base_url
                "type": "list_of_dicts",
                "keys_to_remove": ["unwanted_key"]
            }
        }

    @patch('cleaningApp.views.SOURCE_SERVICES_CLEAN', new_callable=lambda: TestCleaningDataProcessAction.mock_cleaning_rules)
    @patch('cleaningApp.views.SOURCE_SERVICES_TARGET', new_callable=lambda: {TestCleaningDataProcessAction.mock_target_source_path})
    @patch('cleaningApp.views.SOURCE_SERVICES_URL', new_callable=lambda: TestCleaningDataProcessAction.mock_source_services_url)
    @patch('cleaningApp.views.requests.get')
    def test_successful_processing(self, mock_requests_get, mock_ss_url, mock_ss_target, mock_ss_clean):
        # Configure the mock response from the source API
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = { # Matching the structure the view expects
            "data": [
                {
                    "source": self.mock_target_source_full_url, # This source should be processed
                    "result": [{"id": 1, "name": "test1", "unwanted_key": "remove_me"}]
                },
                {
                    "source": f"{self.test_base_url}/other/ignored-source/", # This source should be ignored
                    "result": [{"id": 2, "name": "test2"}]
                }
            ]
        }
        mock_requests_get.return_value = mock_api_response

        response = self.client.post(self.process_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("relevant sources successfully processed", response_data["messages"])

        self.assertEqual(CleaningData.objects.count(), 1)
        created_data = CleaningData.objects.first()
        self.assertEqual(created_data.source, self.mock_target_source_full_url)
        self.assertEqual(created_data.content, [{"id": 1, "name": "test1"}]) # unwanted_key removed

    @patch('cleaningApp.views.requests.get')
    def test_source_api_http_error(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")
        mock_api_response.status_code = 502 # Example error code
        mock_api_response.text = "Source API unavailable"
        mock_requests_get.return_value = mock_api_response

        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Error from source API", response_data["messages"])

    @patch('cleaningApp.views.requests.get')
    def test_source_api_request_exception(self, mock_requests_get):
        mock_requests_get.side_effect = requests.exceptions.RequestException("Connection Failed")

        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Failed to contact source API", response_data["messages"])

    @patch('cleaningApp.views.requests.get')
    def test_unrecognized_data_structure(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"unexpected_key": "unexpected_value"} # Does not match expected structure
        mock_requests_get.return_value = mock_api_response

        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR) # ValueError in _parse leads to 500
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Unrecognized data structure from source API", response_data["messages"])

    @patch('cleaningApp.views.SOURCE_SERVICES_CLEAN', new_callable=lambda: TestCleaningDataProcessAction.mock_cleaning_rules)
    @patch('cleaningApp.views.SOURCE_SERVICES_TARGET', new_callable=lambda: {TestCleaningDataProcessAction.mock_target_source_path})
    @patch('cleaningApp.views.SOURCE_SERVICES_URL', new_callable=lambda: TestCleaningDataProcessAction.mock_source_services_url)
    @patch('cleaningApp.views.requests.get')
    def test_no_relevant_sources_in_api_response(self, mock_requests_get, mock_ss_url, mock_ss_target, mock_ss_clean):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "data": [
                {
                    "source": f"{self.test_base_url}/another/api/", # Not in our mocked SOURCE_SERVICES_TARGET
                    "result": [{"id": 1, "name": "test1"}]
                }
            ]
        }
        mock_requests_get.return_value = mock_api_response

        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK) # Still 200, but should indicate 0 processed
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("Data for 0 relevant sources successfully processed", response_data["messages"])
        self.assertEqual(CleaningData.objects.count(), 0)

    @patch('cleaningApp.views.SOURCE_SERVICES_CLEAN', new_callable=dict) # No cleaning rules
    @patch('cleaningApp.views.SOURCE_SERVICES_TARGET', new_callable=lambda: {TestCleaningDataProcessAction.mock_target_source_path})
    @patch('cleaningApp.views.SOURCE_SERVICES_URL', new_callable=lambda: TestCleaningDataProcessAction.mock_source_services_url)
    @patch('cleaningApp.views.requests.get')
    def test_processing_with_no_cleaning_rules_defined_for_source(self, mock_requests_get, mock_ss_url, mock_ss_target, mock_ss_clean_empty):
        # Source is targeted, but no specific cleaning rules in (empty) SOURCE_SERVICES_CLEAN
        original_content = [{"id": 1, "name": "test_no_rules", "unwanted_key": "should_remain"}]
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "data": [
                {
                    "source": self.mock_target_source_full_url,
                    "result": original_content
                }
            ]
        }
        mock_requests_get.return_value = mock_api_response

        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CleaningData.objects.count(), 1)
        created_data = CleaningData.objects.first()
        self.assertEqual(created_data.content, original_content) # Content should be saved as is
        self.assertIn("unwanted_key", created_data.content[0])
