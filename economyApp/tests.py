from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock
import requests # For mocking exceptions
import os

# Assuming ALPHA_API_KEY and ALPHA_BASE_URL are loaded in views.py using os.getenv
# We will patch these for tests or ensure they are set in test environment if views.py is imported directly.

class TestEconomyViews(TestCase):
    def setUp(self):
        self.client = Client()
        # It's good practice to define these, even if views.py uses os.getenv,
        # to ensure tests are independent of environment variables not set in test runner.
        self.mock_alpha_api_key = "TEST_KEY"
        self.mock_alpha_base_url = "http://mockalphavantage.com"

    # Patch os.getenv where it's used in economyApp.views to control these values
    @patch.dict(os.environ, {
        "ALPHA_API_KEY": "TEST_KEY",
        "ALPHA_BASE_URL": "http://mockalphavantage.com"
    })
    @patch('economyApp.views.requests.get')
    def test_get_economy_fiscal_sentiment(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"data": "fiscal data"}
        mock_requests_get.return_value = mock_api_response

        # Assuming URL is /economy/fiscal/
        response = self.client.get("/economy/fiscal/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertEqual(response_data["data"], {"data": "fiscal data"})
        self.assertIn("Fiscal economy data fetched successfully", response_data["messages"])
        
        # Verify the correct URL was called
        expected_url = f"{self.mock_alpha_base_url}/query?function=NEWS_SENTIMENT&apikey={self.mock_alpha_api_key}&topics=economy_fiscal"
        mock_requests_get.assert_called_once_with(expected_url)

    @patch.dict(os.environ, {
        "ALPHA_API_KEY": "TEST_KEY",
        "ALPHA_BASE_URL": "http://mockalphavantage.com"
    })
    @patch('economyApp.views.requests.get')
    def test_get_economy_monetary_sentiment(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"data": "monetary data"}
        mock_requests_get.return_value = mock_api_response

        response = self.client.get("/economy/monetary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertEqual(response_data["data"], {"data": "monetary data"})
        self.assertIn("Monetary economy data fetched successfully", response_data["messages"])
        
        expected_url = f"{self.mock_alpha_base_url}/query?function=NEWS_SENTIMENT&apikey={self.mock_alpha_api_key}&topics=economy_monetary"
        mock_requests_get.assert_called_once_with(expected_url)

    @patch.dict(os.environ, {
        "ALPHA_API_KEY": "TEST_KEY",
        "ALPHA_BASE_URL": "http://mockalphavantage.com"
    })
    @patch('economyApp.views.requests.get')
    def test_get_economy_macro_sentiment(self, mock_requests_get):
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"data": "macro data"}
        mock_requests_get.return_value = mock_api_response

        response = self.client.get("/economy/macro/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertEqual(response_data["data"], {"data": "macro data"})
        self.assertIn("Macro economy data fetched successfully", response_data["messages"])

        expected_url = f"{self.mock_alpha_base_url}/query?function=NEWS_SENTIMENT&apikey={self.mock_alpha_api_key}&topics=economy_macro"
        mock_requests_get.assert_called_once_with(expected_url)

    @patch.dict(os.environ, {
        "ALPHA_API_KEY": "TEST_KEY",
        "ALPHA_BASE_URL": "http://mockalphavantage.com"
    })
    @patch('economyApp.views.requests.get')
    def test_economy_api_request_exception(self, mock_requests_get):
        mock_requests_get.side_effect = requests.exceptions.RequestException("API Connection Error")

        response = self.client.get("/economy/fiscal/") # Test with one endpoint
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertEqual(response_data["messages"], "API Connection Error")

    @patch.dict(os.environ, {
        "ALPHA_API_KEY": "TEST_KEY_UNSET" # Simulate unset or incorrect key
    })
    @patch('economyApp.views.requests.get')
    def test_economy_api_key_issue_simulation(self, mock_requests_get):
        # This test simulates how the external API might behave with a bad key,
        # usually a 4xx error or specific error message in JSON.
        # Alpha Vantage typically returns a specific JSON error for invalid keys.
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200 # Some APIs return 200 but with an error payload
        mock_api_response.json.return_value = {
            "Information": "The API key is invalid or missing."
        }
        # Or, if it returns an HTTP error for bad keys:
        # mock_api_response.status_code = 401
        # mock_api_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Invalid API Key")
        # mock_api_response.text = "Invalid API Key"

        mock_requests_get.return_value = mock_api_response

        response = self.client.get("/economy/fiscal/")
        # Depending on how _fetch_alpha_vantage_data handles this (e.g., if it checks response content for errors)
        # For now, assuming it returns the JSON as is if status is 200.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        # The success_response wrapper will still make it look like a "success" at transport level
        self.assertEqual(response_data["status"], "success")
        self.assertIn("Information", response_data["data"])
        self.assertEqual(response_data["data"]["Information"], "The API key is invalid or missing.")

        # If the actual API returned a 401 and raise_for_status() was triggered:
        # self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # self.assertIn("Invalid API Key", response.json()["messages"])
