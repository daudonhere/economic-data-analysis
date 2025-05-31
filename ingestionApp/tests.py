from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock
import requests # For mocking exceptions

from ingestionApp.models import IngestionData
from ingestionApp.serializers import GetIngestionDataSerializer, IngestionDataSerializer
# Assuming SERVICES_URL is a list of endpoint paths
from configs.endpoint import SERVICES_URL


class TestIngestionDataViewSetList(TestCase):
    def setUp(self):
        self.client = Client()
        self.data1 = IngestionData.objects.create(content={"key": "value1"}, source="http://example.com/source1")
        self.data2 = IngestionData.objects.create(content={"key": "value2"}, source="http://example.com/source2")
        self.collect_url = "/ingestion/collect/" # Assuming this is the path

    def test_list_ingested_data(self):
        response = self.client.get(self.collect_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        self.assertEqual(response_data.get("status"), "success")
        self.assertEqual(response_data.get("code"), status.HTTP_200_OK)
        self.assertIn("Data fetched successfully.", response_data.get("messages", ""))

        # Serializer for comparison, order might depend on default ordering ('-createdAt')
        # Assuming data2 is newer if created after data1
        expected_data = GetIngestionDataSerializer([self.data2, self.data1], many=True).data
        self.assertEqual(len(response_data["data"]), 2)
        # More robust: check for presence if order isn't strictly guaranteed or tested
        response_sources = [item["source"] for item in response_data["data"]]
        self.assertIn(self.data1.source, response_sources)
        self.assertIn(self.data2.source, response_sources)


class TestIngestionDataProcessAction(TestCase):
    def setUp(self):
        self.client = Client()
        self.process_url = "/ingestion/process/" # Assuming this is the path
        self.test_base_url = "http://testserver" # Django's default test server base

        # Ensure SERVICES_URL is patched if it's dynamically loaded or too extensive
        # For this example, let's assume SERVICES_URL = ["/service1", "/service2"] for mocking
        self.mock_services_url = ["/mockapi/service1", "/mockapi/service2"]


    @patch('ingestionApp.views.SERVICES_URL', new_callable=lambda: TestIngestionDataProcessAction.mock_services_url)
    @patch('ingestionApp.views.requests.get')
    def test_successful_ingestion_all_services(self, mock_requests_get, mock_svc_urls):
        # Mock responses for each service URL
        def side_effect_func(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if url == f"{self.test_base_url}{self.mock_services_url[0]}":
                mock_resp.json.return_value = {"data": {"content": "service1 data"}}
            elif url == f"{self.test_base_url}{self.mock_services_url[1]}":
                mock_resp.json.return_value = {"data": {"content": "service2 data"}}
            else:
                mock_resp.status_code = 404 # Should not happen if SERVICES_URL is patched
                mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("Not Found")
            return mock_resp

        mock_requests_get.side_effect = side_effect_func

        response = self.client.post(self.process_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("All data ingested successfully", response_data["messages"])
        self.assertEqual(IngestionData.objects.count(), 2)
        self.assertTrue(IngestionData.objects.filter(source=f"{self.test_base_url}{self.mock_services_url[0]}").exists())
        self.assertTrue(IngestionData.objects.filter(source=f"{self.test_base_url}{self.mock_services_url[1]}").exists())

    @patch('ingestionApp.views.SERVICES_URL', new_callable=lambda: TestIngestionDataProcessAction.mock_services_url)
    @patch('ingestionApp.views.requests.get')
    def test_all_services_fail(self, mock_requests_get, mock_svc_urls):
        mock_requests_get.side_effect = requests.exceptions.RequestException("Connection Error for all services")

        response = self.client.post(self.process_url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("All requests failed", response_data["messages"])
        self.assertEqual(IngestionData.objects.count(), 0)
        self.assertEqual(len(response_data["data"]["failed_logs"]), len(self.mock_services_url))

    @patch('ingestionApp.views.SERVICES_URL', new_callable=lambda: TestIngestionDataProcessAction.mock_services_url)
    @patch('ingestionApp.views.requests.get')
    def test_partial_success_207(self, mock_requests_get, mock_svc_urls):
        def side_effect_func(url, *args, **kwargs):
            mock_resp = MagicMock()
            if url == f"{self.test_base_url}{self.mock_services_url[0]}": # Success for service1
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"data": {"content": "service1 data"}}
            elif url == f"{self.test_base_url}{self.mock_services_url[1]}": # Failure for service2
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("Service 2 Error")
            return mock_resp

        mock_requests_get.side_effect = side_effect_func

        response = self.client.post(self.process_url)

        self.assertEqual(response.status_code, status.HTTP_207_MULTI_STATUS)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success") # The wrapper status is success for 207
        self.assertIn("Some endpoints succeeded, others failed", response_data["messages"])

        self.assertEqual(IngestionData.objects.count(), 1)
        self.assertTrue(IngestionData.objects.filter(source=f"{self.test_base_url}{self.mock_services_url[0]}").exists())

        data_payload = response_data["data"]
        self.assertEqual(data_payload["success_count"], 1)
        self.assertEqual(data_payload["failed_count"], 1)
        self.assertEqual(len(data_payload["failed_logs"]), 1)
        self.assertEqual(data_payload["failed_logs"][0]["url"], f"{self.test_base_url}{self.mock_services_url[1]}")
        self.assertIn("RequestException: Service 2 Error", data_payload["failed_logs"][0]["error"]) # Error is wrapped
        self.assertEqual(len(data_payload["ingested_data"]), 1)

    @patch('ingestionApp.views.SERVICES_URL', new_callable=list) # Patch with empty list
    @patch('ingestionApp.views.requests.get')
    def test_no_services_defined(self, mock_requests_get, mock_empty_svc_urls):
        response = self.client.post(self.process_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("No endpoints defined or processed", response_data["messages"])
        self.assertEqual(IngestionData.objects.count(), 0)
        # Ensure 'data' is an empty list if 'ingested_data' is not present
        self.assertEqual(response_data.get("data", []), [])
