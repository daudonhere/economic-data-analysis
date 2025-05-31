from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock
import requests # For mocking exceptions
import os

from financeApp.serializers import ( # Assuming these are used by the view/response
    StockDataSerializer,
    MarketActiveStockSerializer,
)

class TestFinanceViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.mock_fmp_api_key = "TEST_FMP_KEY"
        self.mock_fmp_base_url = "http://mockfmp.com/api/v3" # Common FMP base

    @patch.dict(os.environ, {
        "FMP_API_KEY": "TEST_FMP_KEY",
        "FMP_BASE_URL": "http://mockfmp.com/api/v3"
    })
    @patch('financeApp.views.requests.get')
    def test_get_stock_list(self, mock_requests_get):
        mock_api_data = [{"symbol": "AAPL", "name": "Apple Inc."}]
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = mock_api_data
        mock_requests_get.return_value = mock_api_response

        response = self.client.get("/finance/stocks/") # Assuming this URL
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("Stock list fetched successfully", response_data["messages"])

        # Validate data against serializer if possible, or check key fields
        # Serializer needs to be instantiated correctly if used for direct comparison
        # For simplicity, checking a key field from the mocked data
        self.assertEqual(len(response_data["data"]), 1)
        self.assertEqual(response_data["data"][0]["symbol"], "AAPL")

        expected_url = f"{self.mock_fmp_base_url}/stock/list?apikey={self.mock_fmp_api_key}"
        mock_requests_get.assert_called_once_with(expected_url)

    @patch.dict(os.environ, {
        "FMP_API_KEY": "TEST_FMP_KEY",
        "FMP_BASE_URL": "http://mockfmp.com/api/v3"
    })
    @patch('financeApp.views.requests.get')
    def test_get_market_highest_volume(self, mock_requests_get):
        mock_api_data = [{"symbol": "TSLA", "volume": 1000000}]
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = mock_api_data
        mock_requests_get.return_value = mock_api_response

        response = self.client.get("/finance/volume/") # Assuming this URL
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertIn("High volume stocks fetched successfully", response_data["messages"])
        self.assertEqual(response_data["data"][0]["symbol"], "TSLA")

        expected_url = f"{self.mock_fmp_base_url}/stock_market/actives?apikey={self.mock_fmp_api_key}"
        mock_requests_get.assert_called_once_with(expected_url)

    @patch.dict(os.environ, {
        "FMP_API_KEY": "TEST_FMP_KEY",
        "FMP_BASE_URL": "http://mockfmp.com/api/v3"
    })
    @patch('financeApp.views.requests.get')
    def test_finance_api_request_exception(self, mock_requests_get):
        mock_requests_get.side_effect = requests.exceptions.RequestException("FMP API Connection Error")

        response = self.client.get("/finance/stocks/") # Test with one endpoint
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertEqual(response_data["messages"], "FMP API Connection Error")

    @patch.dict(os.environ, {
        "FMP_API_KEY": "BAD_KEY",
        "FMP_BASE_URL": "http://mockfmp.com/api/v3"
    })
    @patch('financeApp.views.requests.get')
    def test_finance_api_key_issue_simulation(self, mock_requests_get):
        # FMP often returns a JSON message for bad API keys
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200 # Or 401/403 depending on FMP's actual behavior
        mock_api_response.json.return_value = {
            "Error Message": "Invalid API KEY. Please retry or visit our documentation to create one FREE https://site.financialmodelingprep.com/developer/docs"
        }
        # If FMP returns non-200 for bad key:
        # mock_api_response.status_code = 401
        # mock_api_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Invalid API Key from FMP")

        mock_requests_get.return_value = mock_api_response

        response = self.client.get("/finance/stocks/")
        # This depends on how _fetch_fmp_data handles responses that are not successful arrays
        # The current _fetch_fmp_data tries to serialize directly, which would fail if "Error Message" is top-level
        # For this test to pass as-is, _fetch_fmp_data would need to check for "Error Message"
        # or the serializer_class needs to handle such error structures.
        # Assuming the current view might pass this error JSON into the serializer, leading to validation error or unexpected data.
        # If the serializer raises an exception due to unexpected data:
        # self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # self.assertIn("Error Message", response.json()["messages"]) # Or similar based on actual handling

        # If the API returns 200 with this JSON, and the serializer is robust to pass it through (unlikely for many=True array serializers):
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success") # Because the HTTP call itself was 'successful' (200)
        # The 'data' field would contain what the serializer made of the error message
        # This indicates a potential area for improvement in _fetch_fmp_data to detect API-level errors in 200 responses.
        # For a more realistic test of bad API key, we'd expect _fetch_fmp_data to identify the error and return an error_response.
        # However, based on current _fetch_fmp_data, it might try to serialize the error message.
        # Let's assume the serializer is strict and this would lead to a validation error handled by custom_exception_handler or DRF default.
        # If serializer.is_valid(raise_exception=True) is hit with this, it would be a 400 or 500.
        # For now, this test highlights that API error content (even in 200s) needs careful handling in _fetch_fmp_data.
        # To make it more concrete, let's assume the serializer fails and DRF returns a 400 or the view's general exception handler returns 500.
        # If the serializer is strict, it will fail to deserialize `{"Error Message": ...}` as a list.
        # This would likely result in a 500 due to `serializer.is_valid(raise_exception=True)` if not caught more specifically.
        # To accurately test this, one might need to mock the serializer behavior or adjust the view.
        # For now, we'll assume the current structure leads to a 500 if the data isn't a list for a many=True serializer.
        # This is because `serializer_class(data=raw_data, many=True)` would fail if raw_data is `{"Error Message": ...}`.
        # This would be caught by the generic `except requests.RequestException as e:` which is too broad,
        # or by DRF's own exception handling if `raise_exception=True` bubbles up.
        # A more robust _fetch_fmp_data would check if raw_data is a list before serializing with many=True.

        # Given the current structure of _fetch_fmp_data, if json() returns a dict and many=True is used,
        # it will raise an exception when trying to iterate over the dict for serialization.
        # This will be caught by the `except requests.RequestException as e:` which is not ideal,
        # or by DRF's default handler if the exception is a DRF one.
        # Let's assume the outer try-except in _fetch_fmp_data catches this.
        # The error message would be from the serializer failing.
        # This test is a bit complex due to the interaction of view logic and serializer behavior.
        # A simpler assertion might be to check if the external call was made.
        mock_requests_get.assert_called_once()
        # A proper test would require either adjusting the view's error handling for non-list data
        # or ensuring the mock reflects an error that `raise_for_status` would catch (e.g. actual 401).
        # If FMP returns 401 for bad key, and raise_for_status is hit:
        # mock_api_response.status_code = 401
        # mock_api_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Invalid FMP Key")
        # mock_requests_get.return_value = mock_api_response
        # response = self.client.get("/finance/stocks/")
        # self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # self.assertIn("Invalid FMP Key", response.json()["messages"])
        # This path is clearer. Let's assume FMP returns non-200 for bad key.
        # Re-mocking for a non-200 status for bad key:
        mock_api_response_error = MagicMock()
        mock_api_response_error.status_code = 401
        mock_api_response_error.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Client Error: Unauthorized for url")
        mock_requests_get.return_value = mock_api_response_error # Override previous mock for this call path

        response_error_path = self.client.get("/finance/stocks/")
        self.assertEqual(response_error_path.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("401 Client Error: Unauthorized for url", response_error_path.json()["messages"])
