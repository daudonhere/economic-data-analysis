from rest_framework.response import Response
from rest_framework import status

def success_response(data=None, message="Operasi berhasil.", http_status=status.HTTP_200_OK):
    return Response({
        "status": "success",
        "message": message,
        "data": data
    }, status=http_status)

def error_response(message="Terjadi kesalahan.", errors=None, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({
        "status": "error",
        "message": message,
        "errors": errors
    }, status=http_status)