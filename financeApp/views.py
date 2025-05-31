from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response
from common.serializers import ErrorResponseSerializer # Import common error serializer
from financeApp.serializers import (
    StockDataSerializer,
    MarketActiveStockSerializer,
    SectorPerformanceSerializer,
    CryptoDataSerializer,
    DowntrendStockSerializer,
)
import os
import requests
from dotenv import load_dotenv

load_dotenv()

FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_BASE_URL = os.getenv("FMP_BASE_URL")

def _generate_finance_schema(summary: str, description: str, response_serializer_class):
    """Helper function to generate extend_schema arguments for finance data endpoints."""
    return extend_schema(
        summary=summary,
        description=description,
        tags=["Finance Raw Data"],
        responses={
            200: OpenApiResponse(response=response_serializer_class),
            500: OpenApiResponse(description="Internal server error", response=ErrorResponseSerializer),
        }
    )

class FinancialDataViewSet(viewsets.ViewSet):
    def _fetch_fmp_data(self, api_path: str, serializer_class, success_message: str, data_limit: int = None):
        url = f"{FMP_BASE_URL}/{api_path}?apikey={FMP_API_KEY}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            raw_data = response.json()

            if data_limit is not None:
                raw_data = raw_data[:data_limit]

            # For list views, serializer_class is already many=True from the decorator
            # For single object views (not present here), it would be serializer_class(data=raw_data)
            serializer = serializer_class(data=raw_data) if not isinstance(serializer_class, type) and serializer_class.many else serializer_class(data=raw_data, many=True)

            serializer.is_valid(raise_exception=True)

            return success_response(data=serializer.data, message=success_message)
        except requests.RequestException as e:
            return error_response(message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @_generate_finance_schema(
        summary="Most searched stocks",
        description="Returns a list of the most searched stocks",
        response_serializer_class=StockDataSerializer(many=True)
    )
    @action(detail=False, methods=["get"], url_path="stocks")
    def get_stock_list(self, request):
        return self._fetch_fmp_data(
            api_path="stock/list",
            serializer_class=StockDataSerializer, # Pass the class, not instance
            success_message="Stock list fetched successfully.",
            data_limit=100
        )

    @_generate_finance_schema(
        summary="Market highest volume",
        description="Returns a list of stocks with highest trading volume",
        response_serializer_class=MarketActiveStockSerializer(many=True)
    )
    @action(detail=False, methods=["get"], url_path="volume")
    def get_market_highest_volume(self, request):
        return self._fetch_fmp_data(
            api_path="stock_market/actives",
            serializer_class=MarketActiveStockSerializer, # Pass the class
            success_message="High volume stocks fetched successfully."
        )

    @_generate_finance_schema(
        summary="Most sector performance",
        description="Returns performance change for each sector",
        response_serializer_class=SectorPerformanceSerializer(many=True)
    )
    @action(detail=False, methods=["get"], url_path="sector")
    def get_sector_performance(self, request):
        return self._fetch_fmp_data(
            api_path="sector-performance",
            serializer_class=SectorPerformanceSerializer, # Pass the class
            success_message="Sector performance data retrieved."
        )

    @_generate_finance_schema(
        summary="Most traded cryptocurrencies",
        description="Returns a list of most traded cryptocurrency",
        response_serializer_class=CryptoDataSerializer(many=True)
    )
    @action(detail=False, methods=["get"], url_path="crypto")
    def get_crypto_symbols(self, request):
        return self._fetch_fmp_data(
            api_path="symbol/available-cryptocurrencies",
            serializer_class=CryptoDataSerializer, # Pass the class
            success_message="Cryptocurrency data fetched.",
            data_limit=100
        )

    @_generate_finance_schema(
        summary="Most stocks downtrend",
        description="Returns a list of stocks with the highest negative price changes",
        response_serializer_class=DowntrendStockSerializer(many=True)
    )
    @action(detail=False, methods=["get"], url_path="downtrend")
    def get_top_losers(self, request):
        return self._fetch_fmp_data(
            api_path="stock_market/losers",
            serializer_class=DowntrendStockSerializer, # Pass the class
            success_message="Top downtrend stocks retrieved.",
            data_limit=100
        )
