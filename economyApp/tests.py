import os
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
import requests # Required for requests.exceptions.RequestException

# Ensure .env is loaded for tests if not already handled by manage.py test
from dotenv import load_dotenv
load_dotenv()


class AnalyticSentimentViewSetTests(APITestCase):
    @patch('economyApp.views.requests.get')
    def test_get_economy_fiscal_sentiment_success(self, mock_get):
        # Configure the mock_get object for a successful response
        mock_response_data = {'some': 'data', 'feed': [{'title': 'Fiscal News'}]}
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = mock_response_data
        # mock_api_response.raise_for_status = MagicMock() # Not strictly needed if status_code is 200
        mock_get.return_value = mock_api_response

        # Define expected values
        expected_success_message = "Fiscal economy data fetched successfully"
        url = reverse('economyApp:economy-fiscal') # as derived

        # Make the GET request
        response = self.client.get(url)

        # Assert response status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Assert response data structure
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['messages'], expected_success_message)
        self.assertEqual(response.data['data'], mock_response_data)

        # Assert that requests.get was called correctly
        ALPHA_API_KEY = os.getenv("ALPHA_API_KEY")
        ALPHA_BASE_URL = os.getenv("ALPHA_BASE_URL")
        # Ensure these are not None for the test to be meaningful
        self.assertIsNotNone(ALPHA_API_KEY, "ALPHA_API_KEY should be set in environment for this test")
        self.assertIsNotNone(ALPHA_BASE_URL, "ALPHA_BASE_URL should be set in environment for this test")
        
        expected_url = f"{ALPHA_BASE_URL}/query?function=NEWS_SENTIMENT&apikey={ALPHA_API_KEY}&topics=economy_fiscal"
        mock_get.assert_called_once_with(expected_url)
        mock_api_response.raise_for_status.assert_called_once()


    @patch('economyApp.views.requests.get')
    def test_get_economy_fiscal_sentiment_api_error(self, mock_get):
        # Configure the mock_get to raise a requests.exceptions.RequestException
        api_error_message = "API connection error"
        mock_get.side_effect = requests.exceptions.RequestException(api_error_message)

        # Define the URL
        url = reverse('economyApp:economy-fiscal')

        # Make the GET request
        response = self.client.get(url)

        # Assert response status code
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Assert response data structure
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['messages'], api_error_message)
        self.assertIsNone(response.data['data'])
        
        # Assert that requests.get was called (even though it failed)
        ALPHA_API_KEY = os.getenv("ALPHA_API_KEY")
        ALPHA_BASE_URL = os.getenv("ALPHA_BASE_URL")
        # Ensure these are not None for the test to be meaningful
        self.assertIsNotNone(ALPHA_API_KEY, "ALPHA_API_KEY should be set in environment for this test")
        self.assertIsNotNone(ALPHA_BASE_URL, "ALPHA_BASE_URL should be set in environment for this test")

        expected_url = f"{ALPHA_BASE_URL}/query?function=NEWS_SENTIMENT&apikey={ALPHA_API_KEY}&topics=economy_fiscal"
        mock_get.assert_called_once_with(expected_url)

    @patch('economyApp.views.requests.get')
    def test_get_economy_fiscal_sentiment_http_error(self, mock_get):
        # Configure the mock_get object for a failed HTTP response (e.g., 401, 403, 429)
        mock_api_response = MagicMock()
        mock_api_response.status_code = 401 # Example: Unauthorized
        mock_api_response.reason = "Unauthorized"
        mock_api_response.json.return_value = {'error': 'Invalid API Key'}
        # Configure raise_for_status to simulate an HTTPError
        mock_api_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{mock_api_response.status_code} Client Error: {mock_api_response.reason} for url: FAKE_URL", 
            response=mock_api_response
        )
        mock_get.return_value = mock_api_response

        url = reverse('economyApp:economy-fiscal')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['status'], 'error')
        # The message in error_response comes from str(e), where e is RequestException.
        # For HTTPError, this string representation includes the status code, reason, and URL.
        self.assertTrue(f"{mock_api_response.status_code} Client Error: {mock_api_response.reason}" in response.data['messages'])
        self.assertIsNone(response.data['data'])

        ALPHA_API_KEY = os.getenv("ALPHA_API_KEY")
        ALPHA_BASE_URL = os.getenv("ALPHA_BASE_URL")
        expected_url = f"{ALPHA_BASE_URL}/query?function=NEWS_SENTIMENT&apikey={ALPHA_API_KEY}&topics=economy_fiscal"
        mock_get.assert_called_once_with(expected_url)
        mock_api_response.raise_for_status.assert_called_once()
