from rest_framework import status, viewsets
from rest_framework.decorators import action
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiResponse
from ingestionApp.models import IngestionData
from cleaningApp.models import CleaningData
from transformationApp.models import TransformationData
from visualizationApp.models import VisualizationData
from .serializers import GlobalDeleteSerializer
from .utils import success_response, error_response

class DeleteAllDataViewSet(viewsets.ViewSet):
    @extend_schema(
        summary="Delete All Data",
        description="Delete all data entry",
        tags=["Delete Resource"],
        responses={
            200: OpenApiResponse(
                response=GlobalDeleteSerializer,
                description="All data successfully deleted."
            ),
            500: OpenApiResponse(description="Something went wrong, please try again later.")
        }
    )
    @action(detail=False, methods=["delete"], url_path="resource")
    def delete_all_data(self, request):
        serializer = GlobalDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deleted_counts = {}
        try:
            with transaction.atomic():
                viz_deleted_count, _ = VisualizationData.objects.all().delete()
                deleted_counts['VisualizationData'] = viz_deleted_count
                clean_deleted_count, _ = CleaningData.objects.all().delete()
                deleted_counts['CleaningData'] = clean_deleted_count
                trans_deleted_count, _ = TransformationData.objects.all().delete()
                deleted_counts['TransformationData'] = trans_deleted_count
                ing_deleted_count, _ = IngestionData.objects.all().delete()
                deleted_counts['IngestionData'] = ing_deleted_count
                total_deleted_entries = sum(deleted_counts.values())
                message = f"All data successfully deleted. Total {total_deleted_entries} entri deleted."
                return success_response(message=message, data=deleted_counts)

        except Exception as e:
            return error_response(
                message=f"Something went wrong, please try again later. Error: {str(e)}",
                errors={"detail": str(e)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )