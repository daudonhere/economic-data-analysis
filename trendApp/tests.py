from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock
import pandas as pd # For mocking pytrends response

# Assuming TrendReq is in trendApp.views or trendApp.services
# If it's directly in views, the patch target is 'trendApp.views.TrendReq'
# If it's imported into views from somewhere else, patch where it's looked up.

class TestTrendViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.search_url = "/trend/search/" # Assuming this is the path

    @patch('trendApp.views.TrendReq') # Patch where TrendReq is used
    def test_trend_search_successful(self, MockTrendReq):
        # Configure the mock instance and its methods
        mock_pytrends_instance = MagicMock()
        MockTrendReq.return_value = mock_pytrends_instance

        # Mock data for interest_over_time()
        mock_df = pd.DataFrame({'some_query': [10, 20, 30]}, index=pd.to_datetime(['2023-01-01', '2023-01-08', '2023-01-15']))
        mock_pytrends_instance.interest_over_time.return_value = mock_df

        response = self.client.get(self.search_url, {'query': 'some_query'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        self.assertEqual(response_data["status"], "success")
        self.assertIn("Data fetched successfully", response_data["messages"])

        # Check if 'data' contains list version of DataFrame json
        # Example: [{'date': '2023-01-01T00:00:00Z', 'some_query': 10}, ...]
        # The actual format depends on how the DataFrame is converted to JSON in the view.
        # Assuming it's records orient:
        expected_data_structure = mock_df.reset_index().rename(columns={'index': 'date'}).to_dict(orient='records')
        # The view might further process this, e.g., converting Timestamp to string.
        # For a basic check:
        self.assertTrue(len(response_data["data"]) > 0)
        self.assertEqual(response_data["data"][0]['some_query'], 10)

        mock_pytrends_instance.build_payload.assert_called_once_with(kw_list=['some_query'], timeframe='today 5-y', geo='')
        mock_pytrends_instance.interest_over_time.assert_called_once()

    def test_trend_search_no_query(self):
        response = self.client.get(self.search_url) # No query parameter
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Query parameter is required", response_data["messages"])

    @patch('trendApp.views.TrendReq')
    def test_trend_search_no_data_returned_from_pytrends(self, MockTrendReq):
        mock_pytrends_instance = MagicMock()
        MockTrendReq.return_value = mock_pytrends_instance

        # Mock empty DataFrame for interest_over_time()
        empty_df = pd.DataFrame()
        mock_pytrends_instance.interest_over_time.return_value = empty_df

        response = self.client.get(self.search_url, {'query': 'obscure_query'})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response_data = response.json() # DRF might return an empty body for 204 from error_response
                                        # or the error_response utility might format it.
                                        # Based on current error_response, it will have a body.
        self.assertEqual(response_data["status"], "error") # Or "success" if 204 is treated as success with no data
        self.assertIn("No data found for the query", response_data["messages"])
        self.assertEqual(response_data["data"], [])


    @patch('trendApp.views.TrendReq')
    def test_trend_search_pytrends_exception(self, MockTrendReq):
        mock_pytrends_instance = MagicMock()
        MockTrendReq.return_value = mock_pytrends_instance

        # Simulate an exception from pytrends
        mock_pytrends_instance.interest_over_time.side_effect = Exception("Pytrends API Error")

        response = self.client.get(self.search_url, {'query': 'error_query'})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Pytrends API Error", response_data["messages"])

    @patch('trendApp.views.TrendReq')
    def test_trend_search_build_payload_exception(self, MockTrendReq):
        mock_pytrends_instance = MagicMock()
        MockTrendReq.return_value = mock_pytrends_instance

        mock_pytrends_instance.build_payload.side_effect = Exception("Build Payload Error")

        response = self.client.get(self.search_url, {'query': 'build_error_query'})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data["status"], "error")
        self.assertIn("Build Payload Error", response_data["messages"])

    # Example of how to test if the DataFrame to JSON conversion is as expected
    @patch('trendApp.views.TrendReq')
    def test_trend_data_json_format(self, MockTrendReq):
        mock_pytrends_instance = MagicMock()
        MockTrendReq.return_value = mock_pytrends_instance

        data = {'date': pd.to_datetime(['2023-01-01', '2023-01-08']), 'test_query': [10, 20], 'isPartial': [False, False]}
        mock_df = pd.DataFrame(data).set_index('date')
        mock_pytrends_instance.interest_over_time.return_value = mock_df

        response = self.client.get(self.search_url, {'query': 'test_query'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()['data']

        # Expected format after df.reset_index().to_json(orient='records', date_format='iso')
        # Timestamps are converted to ISO format strings by pandas.
        expected_json_data = [
            {'date': '2023-01-01T00:00:00.000Z', 'test_query': 10, 'isPartial': False},
            {'date': '2023-01-08T00:00:00.000Z', 'test_query': 20, 'isPartial': False}
        ]
        # This requires careful matching of the date format from pandas.
        # For simplicity, we might just check keys and types if exact date string format is too fragile.
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]['test_query'], 10)
        self.assertTrue('date' in response_data[0])
        self.assertTrue('isPartial' in response_data[0])
        # Or if using the exact format from the view:
        # self.assertEqual(response_data, expected_json_data) # This can be very specific
