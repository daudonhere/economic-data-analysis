from django.urls import path, include
from rest_framework.routers import DefaultRouter
from transformedApp.views import CleansedDataViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'transformed', CleansedDataViewSet, basename='transformed')

transformedApp_urlpatterns = [
    path('', include(router.urls)),
]