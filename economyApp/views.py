from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
import os
import requests
from dotenv import load_dotenv
from configs.utils import success_response, error_response

load_dotenv()

ALPHA_API_KEY = os.getenv("ALPHA_API_KEY")
ALPHA_BASE_URL = os.getenv("ALPHA_BASE_URL")

class AnalyticSentimentViewSet(viewsets.ViewSet):
    def _fetch_alpha_vantage_data(self, topics: str, success_message: str):
        url = f"{ALPHA_BASE_URL}/query?function=NEWS_SENTIMENT&apikey={ALPHA_API_KEY}&topics={topics}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return success_response(data=data, message=success_message)
        except requests.RequestException as e:
            return error_response(message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Most trend topics about fiscal economics",
        description="Returns fiscal economic data analysis.",
        tags=["Economic Raw Data"],
        responses={
            200: OpenApiResponse(description="Success response"),
            500: OpenApiResponse(description="Internal server error")
        }
    )
    @action(detail=False, methods=["get"], url_path="fiscal")
    def get_economy_fiscal_sentiment(self, request):
        return self._fetch_alpha_vantage_data(topics="economy_fiscal", success_message="Fiscal economy data fetched successfully")

    @extend_schema(
        summary="Data monetary economics and public responses",
        description="Returns monetary economic data analysis.",
        tags=["Economic Raw Data"],
        responses={
            200: OpenApiResponse(description="Success response"),
            500: OpenApiResponse(description="Internal server error")
        }
    )
    @action(detail=False, methods=["get"], url_path="monetary")
    def get_economy_monetary_sentiment(self, request):
        return self._fetch_alpha_vantage_data(topics="economy_monetary", success_message="Monetary economy data fetched successfully")

    @extend_schema(
        summary="Most trend about macro economics",
        description="Return macro economic data analysis and public response",
        tags=["Economic Raw Data"],
        responses={
            200: OpenApiResponse(description="Success response"),
            500: OpenApiResponse(description="Internal server error")
        }
    )
    @action(detail=False, methods=["get"], url_path="macro")
    def get_economy_macro_sentiment(self, request):
        return self._fetch_alpha_vantage_data(topics="economy_macro", success_message="Macro economy data fetched successfully")
