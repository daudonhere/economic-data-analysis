from django.urls import path, include
from rest_framework.routers import DefaultRouter
from restoreApp.views import DeleteAllDataViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r'delete', DeleteAllDataViewSet, basename='delete')
restoreApp_urlpatterns = [
    path('', include(router.urls)),
]
