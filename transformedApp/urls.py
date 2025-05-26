from django.urls import path, include
from rest_framework.routers import DefaultRouter
from transformedApp.views import DataTransformationViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'transformed', DataTransformationViewSet, basename='transformed')

transformedApp_urlpatterns = [
    path('', include(router.urls)),
]