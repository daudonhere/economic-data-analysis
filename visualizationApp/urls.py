from django.urls import path, include
from rest_framework.routers import DefaultRouter
from visualizationApp.views import VisualizationAnalysisViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r'visualization', VisualizationAnalysisViewSet, basename='visualization')

visualizationApp_urlpatterns = [
    path('', include(router.urls)),
]
