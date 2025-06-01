from django.urls import path, include
from rest_framework.routers import DefaultRouter
from transformationApp.views import DataTransformationViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'transformation', DataTransformationViewSet, basename='transformation')

transformationApp_urlpatterns = [
    path('', include(router.urls)),
]