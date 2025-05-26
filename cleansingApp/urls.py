from django.urls import path, include
from rest_framework.routers import DefaultRouter
from cleansingApp.views import CleansedDataViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'cleansing', CleansedDataViewSet, basename='cleansing')

cleansingApp_urlpatterns = [
    path('', include(router.urls)),
]