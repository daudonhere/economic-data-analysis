from django.urls import path, include
from rest_framework.routers import DefaultRouter
from financeApp.views import FinancialDataViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r'finance', FinancialDataViewSet, basename='finance')

financeApp_urlpatterns = [
    path('', include(router.urls)),
]
