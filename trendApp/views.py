from rest_framework import status, viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from pytrends.request import TrendReq
from trendApp.serializers import TrendingTopicSerializer
from configs.utils import success_response, error_response

class SearchTrendViewSet(viewsets.ViewSet):
    pytrends = TrendReq(hl='en-US', tz=360)

    @extend_schema(
        summary="Most searched on google",
        description="Showing the most search data trends related to economics and finance",
        tags=["Data Trending"],
        parameters=[
            OpenApiParameter(name="query", description="search query", required=True, type=str),
        ],
        responses={
            200: OpenApiResponse(response=TrendingTopicSerializer(many=True)),
            204: OpenApiResponse(description="There is no data for this query"),
            400: OpenApiResponse(description="Query parameter is required"),
            500: OpenApiResponse(description="An error occurred on the server.")
        }
    )
    @action(detail=False, methods=["get"], url_path="search")
    def trending_topic(self, request):
        query = request.query_params.get("query")
        if not query:
            return error_response(message="Query parameter is required.", code=status.HTTP_400_BAD_REQUEST)

        try:
            category = 7
            timeframe = 'now 7-d'
            geo = ''
            gprop = ''

            self.pytrends.build_payload(
                kw_list=[query],
                cat=category,
                timeframe=timeframe,
                geo=geo,
                gprop=gprop
            )

            df = self.pytrends.interest_over_time()

            if df.empty or query not in df.columns:
                return error_response(message=f"There is no data for '{query}'.", code=status.HTTP_204_NO_CONTENT)

            trend_data = []
            max_value = df[query].max()
            for date, row in df.iterrows():
                value = int(row[query])
                trend_data.append({
                    "trend": query,
                    "value": value,
                    "startFrom": date.isoformat(),
                    "volume": f"{value * 1000}",
                    "dayName": date.strftime('%A'),
                    "hour": date.hour,
                    "percentage": f"{round((value / max_value) * 100)}%",
                    "is_peak": value == max_value
                })

            serializer = TrendingTopicSerializer(data=trend_data, many=True)
            serializer.is_valid(raise_exception=True)
            return success_response(data=serializer.data, message="Trending data fetched successfully")

        except Exception as e:
            return error_response(message=f"Exception: {str(e)}", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
