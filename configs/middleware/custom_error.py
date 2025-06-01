from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

class Middleware(MiddlewareMixin):
    def process_response(self, request, response):
        if response.status_code in [400, 403, 404, 500] and "text/html" in response.get("Content-Type", ""):
            return render(
                request, 
                "error.html", 
                {"status_code": response.status_code, "error_message": response.reason_phrase},
                status=response.status_code,
            )
        return response

    def process_exception(self, request, exception):
        return render(
            request,
            "error.html",
            {"status_code": 500, "error_message": str(exception)},
            status=500,
        )