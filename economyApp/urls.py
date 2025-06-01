from django.urls import path, include
from rest_framework.routers import DefaultRouter
from economyApp.views import AnalyticSentimentViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r'economy', AnalyticSentimentViewSet, basename='economy')

economyApp_urlpatterns = [
    path('', include(router.urls)),
]
