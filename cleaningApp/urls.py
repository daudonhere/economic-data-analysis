from django.urls import path, include
from rest_framework.routers import DefaultRouter
from cleaningApp.views import CleaningDataViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'cleaning', CleaningDataViewSet, basename='cleaning')

cleaningApp_urlpatterns = [
    path('', include(router.urls)),
]