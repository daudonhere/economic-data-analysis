from django.urls import path, include
from rest_framework.routers import DefaultRouter
from trendApp.views import SearchTrendViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r'trending', SearchTrendViewSet, basename='trending')

trendApp_urlpatterns = [
    path('', include(router.urls)),
]
