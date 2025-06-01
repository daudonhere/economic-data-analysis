from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ingestionApp.views import IngestionDataViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'ingestion', IngestionDataViewSet, basename='ingestion')

ingestionApp_urlpatterns = [
    path('', include(router.urls)),
]