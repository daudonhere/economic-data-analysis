from rest_framework import status
from configs.utils import success_response, error_response
# Note: No action or extend_schema needed here as per refined plan.
# Specific ViewSets will decorate their own actions.

class ListModelMixin:
    """
    A mixin that provides a reusable method to list all items from a queryset.
    Assumes the ViewSet using it defines:
    - self.serializer_class: The serializer for individual model instances.
    - self.get_queryset(): A method that returns the base queryset.
    """

    def _list_all_items(self, request, order_by_field='-createdAt'):
        """
        Core logic to list, serialize, and return data.
        The ViewSet's action method will handle @action and @extend_schema.
        """
        try:
            # These must be defined by the consuming ViewSet
            if not hasattr(self, 'get_queryset'):
                raise NotImplementedError("ViewSet must implement get_queryset()")
            if not hasattr(self, 'serializer_class'):
                raise NotImplementedError("ViewSet must define serializer_class attribute")

            queryset = self.get_queryset().order_by(order_by_field)
            serializer = self.serializer_class(queryset, many=True)

            return success_response(
                data=serializer.data,
                message="Data fetched successfully.", # Generic message, can be overridden by ViewSet if needed
                code=status.HTTP_200_OK
            )
        except NotImplementedError as nie: # To catch the specific errors from above
            return error_response(
                message=str(nie),
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            # More specific error message can be provided by the calling ViewSet if it has more context
            return error_response(
                message=f"Failed to fetch data: {str(e)}",
                data=[], # Consistent with original implementations
                code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
