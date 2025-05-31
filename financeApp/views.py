from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from configs.utils import success_response, error_response
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

class FinancialDataViewSet(viewsets.ViewSet):
    def _fetch_fmp_data(self, api_path: str, serializer_class, success_message: str, data_limit: int = None):
        url = f"{FMP_BASE_URL}/{api_path}?apikey={FMP_API_KEY}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            raw_data = response.json()

            if data_limit is not None:
                raw_data = raw_data[:data_limit]

            serializer = serializer_class(data=raw_data, many=True)
            serializer.is_valid(raise_exception=True)

            return success_response(data=serializer.data, message=success_message)
        except requests.RequestException as e:
            return error_response(message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Most searched stocks",
        description="Returns a list of the most searched stocks",
        tags=["Finance Raw Data"],
        responses={
            200: OpenApiResponse(response=StockDataSerializer(many=True)),
            500: OpenApiResponse(description="Internal server error"),
        },
    )
    @action(detail=False, methods=["get"], url_path="stocks")
    def get_stock_list(self, request):
        return self._fetch_fmp_data(
            api_path="stock/list",
            serializer_class=StockDataSerializer,
            success_message="Stock list fetched successfully.",
            data_limit=100
        )

    @extend_schema(
        summary="Market highest volume",
        description="Returns a list of stocks with highest trading volume",
        tags=["Finance Raw Data"],
        responses={
            200: OpenApiResponse(response=MarketActiveStockSerializer(many=True)),
            500: OpenApiResponse(description="Internal server error"),
        },
    )
    @action(detail=False, methods=["get"], url_path="volume")
    def get_market_highest_volume(self, request):
        return self._fetch_fmp_data(
            api_path="stock_market/actives",
            serializer_class=MarketActiveStockSerializer,
            success_message="High volume stocks fetched successfully."
        )

    @extend_schema(
        summary="Most sector performance",
        description="Returns performance change for each sector",
        tags=["Finance Raw Data"],
        responses={
            200: OpenApiResponse(response=SectorPerformanceSerializer(many=True)),
            500: OpenApiResponse(description="Internal server error"),
        },
    )
    @action(detail=False, methods=["get"], url_path="sector")
    def get_sector_performance(self, request):
        return self._fetch_fmp_data(
            api_path="sector-performance",
            serializer_class=SectorPerformanceSerializer,
            success_message="Sector performance data retrieved."
        )

    @extend_schema(
        summary="Most traded cryptocurrencies",
        description="Returns a list of most traded cryptocurrency",
        tags=["Finance Raw Data"],
        responses={
            200: OpenApiResponse(response=CryptoDataSerializer(many=True)),
            500: OpenApiResponse(description="Internal server error"),
        },
    )
    @action(detail=False, methods=["get"], url_path="crypto")
    def get_crypto_symbols(self, request):
        return self._fetch_fmp_data(
            api_path="symbol/available-cryptocurrencies",
            serializer_class=CryptoDataSerializer,
            success_message="Cryptocurrency data fetched.",
            data_limit=100
        )

    @extend_schema(
        summary="Most stocks downtrend",
        description="Returns a list of stocks with the highest negative price changes",
        tags=["Finance Raw Data"],
        responses={
            200: OpenApiResponse(response=DowntrendStockSerializer(many=True)),
            500: OpenApiResponse(description="Internal Server Error"),
        },
    )
    @action(detail=False, methods=["get"], url_path="downtrend")
    def get_top_losers(self, request):
        return self._fetch_fmp_data(
            api_path="stock_market/losers",
            serializer_class=DowntrendStockSerializer,
            success_message="Top downtrend stocks retrieved.",
            data_limit=100
        )
