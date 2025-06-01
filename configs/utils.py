from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework import status

def success_response(data, message="Request successful", code=200):
    return Response({
        "data": data,
        "status": "success",
        "code": code,
        "messages": message
    }, status=code)

def error_response(message="Request failed", code=400, data=None):
    return Response({
        "data": data,
        "status": "error",
        "code": code,
        "messages": message
    }, status=code)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            "data": None,
            "status": "error",
            "code": response.status_code,
            "messages": response.data.get("detail", "An error occurred"),
        }
        return Response(custom_response_data, status=response.status_code)

    return response
