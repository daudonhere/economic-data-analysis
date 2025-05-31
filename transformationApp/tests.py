from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock
from decimal import Decimal
import requests # For mocking exceptions

from transformationApp.models import TransformationData
from transformationApp.serializers import TransformationDataSerializer
from configs.endpoint import SERVICES_TRANSFORMATION_PATH # This is the cleaningApp collect URL
# from common.utils import extract_text_from_json_content # Not directly used in tests, but by view

class TestTransformationDataViewSetList(TestCase):
    def setUp(self):
        self.client = Client()
        self.data1 = TransformationData.objects.create(
            content={"text": "original data 1"},
            source="http://example.com/cleaning/source1",
            frequency=Decimal("1.23"),
            percentage=Decimal("0.00")
        )
        self.data2 = TransformationData.objects.create(
            content={"text": "original data 2"},
            source="http://example.com/cleaning/source2",
            frequency=Decimal("4.56"),
            percentage=Decimal("10.50")
        )
        self.collect_url = "/transformation/collect/"

    def test_list_transformation_data(self):
        response = self.client.get(self.collect_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        self.assertEqual(response_data.get("status"), "success")
        self.assertEqual(response_data.get("code"), status.HTTP_200_OK)
        self.assertIn("Data fetched successfully.", response_data.get("messages", ""))

        expected_data = TransformationDataSerializer([self.data2, self.data1], many=True).data # Assuming -createdAt
        self.assertEqual(len(response_data["data"]), 2)
        response_sources = [item["source"] for item in response_data["data"]]
        self.assertIn(self.data1.source, response_sources)
        self.assertIn(self.data2.source, response_sources)

class TestTransformationProcessAction(TestCase):
    def setUp(self):
        self.client = Client()
        self.process_url = "/transformation/process/"
        self.mock_cleaning_api_url = f"http://testserver{SERVICES_TRANSFORMATION_PATH}"

    @patch('transformationApp.views.SKLEARN_AVAILABLE', True)
    @patch('transformationApp.views.requests.get')
    def test_successful_transformation(self, mock_requests_get_cleaning, mock_sklearn_true):
        mock_cleaning_response = MagicMock()
        mock_cleaning_response.status_code = 200
        # This is data from CleaningApp's /collect endpoint
        mock_cleaning_response.json.return_value = {
            "status": "success", "code": 200, "messages": "Cleaned data fetched",
            "data": [
                {"id": "uuid1", "source": "http://example.com/source1", "result": {"title": "Sample Text", "body": "More sample text for TF-IDF."}},
                {"id": "uuid2", "source": "http://example.com/source2", "result": {"description": "Another item here"}}
            ]
        }
        mock_requests_get_cleaning.return_value = mock_cleaning_response

        # Mock previous TransformationData for percentage change calculation if needed
        # For simplicity, assume no previous data for source1, and one for source2
        TransformationData.objects.create(
            source="http://example.com/source2",
            content={"description": "Old data"},
            frequency=Decimal("0.50"), # Arbitrary previous frequency
            percentage=Decimal("0.0")
        )

        response = self.client.post(self.process_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("Successfully processed and stored", response_data["messages"])

        self.assertEqual(TransformationData.objects.count(), 3) # 1 existing + 2 new

        # Check data for source1 (new)
        data_s1 = TransformationData.objects.filter(source="http://example.com/source1").first()
        self.assertIsNotNone(data_s1)
        self.assertTrue(data_s1.frequency > Decimal("0.00")) # TF-IDF should yield some value
        self.assertEqual(data_s1.percentage, Decimal("0.00")) # No previous record, so 0% change

        # Check data for source2 (updated, percentage change expected)
        data_s2_new = TransformationData.objects.filter(source="http://example.com/source2").order_by('-createdAt').first()
        self.assertIsNotNone(data_s2_new)
        self.assertTrue(data_s2_new.frequency > Decimal("0.00"))
        if data_s2_new.frequency > Decimal("0.50"):
             self.assertTrue(data_s2_new.percentage > Decimal("0.00"))
        elif data_s2_new.frequency < Decimal("0.50"):
             self.assertTrue(data_s2_new.percentage < Decimal("0.00"))
        # Note: Exact TF-IDF values depend on scikit-learn's internal calculations for simple text,
        # so we check for non-zero frequency and logical percentage change.

    @patch('transformationApp.views.SKLEARN_AVAILABLE', False)
    def test_sklearn_not_available(self, mock_sklearn_false):
        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("TF-IDF calculation engine (scikit-learn) is not available", response_data["messages"])

    @patch('transformationApp.views.SKLEARN_AVAILABLE', True)
    @patch('transformationApp.views.requests.get')
    def test_error_from_cleaning_data_api(self, mock_requests_get_cleaning, mock_sklearn_true):
        mock_cleaning_response = MagicMock()
        mock_cleaning_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Cleaning API Error")
        mock_cleaning_response.status_code = 502
        mock_cleaning_response.text = "Cleaning API is down"
        mock_requests_get_cleaning.return_value = mock_cleaning_response

        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Error from cleaning data API", response_data["messages"])

    @patch('transformationApp.views.SKLEARN_AVAILABLE', True)
    @patch('transformationApp.views.requests.get')
    def test_no_data_from_cleaning_api(self, mock_requests_get_cleaning, mock_sklearn_true):
        mock_cleaning_response = MagicMock()
        mock_cleaning_response.status_code = 200
        mock_cleaning_response.json.return_value = {"data": []} # Empty list from cleaning
        mock_requests_get_cleaning.return_value = mock_cleaning_response

        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("No data received from cleaning data API to process", response_data["messages"])
        self.assertEqual(TransformationData.objects.count(), 0)

    @patch('transformationApp.views.SKLEARN_AVAILABLE', True)
    @patch('transformationApp.views.requests.get')
    def test_unexpected_structure_from_cleaning_api(self, mock_requests_get_cleaning, mock_sklearn_true):
        mock_cleaning_response = MagicMock()
        mock_cleaning_response.status_code = 200
        # This structure will cause _fetch_cleaning_data to raise ValueError
        mock_cleaning_response.json.return_value = {"unexpected_format": "true"}
        mock_requests_get_cleaning.return_value = mock_cleaning_response

        response = self.client.post(self.process_url)
        # The ValueError in _fetch_cleaning_data is caught by the generic Exception handler in process_and_store_from_cleaning
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Unexpected data structure from cleaning data API.", response_data["messages"])
        self.assertEqual(TransformationData.objects.count(), 0)
