"""Very small CORS middleware stub used for testing."""

from django.http import HttpResponse


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse(status=200)
        else:
            response = self.get_response(request)

        origin = request.headers.get("Origin", "*")
        response.setdefault("Access-Control-Allow-Origin", origin)
        response.setdefault(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, PATCH, DELETE"
        )
        allowed_headers = request.headers.get(
            "Access-Control-Request-Headers", "origin, content-type, accept, authorization"
        )
        response.setdefault("Access-Control-Allow-Headers", allowed_headers)
        response.setdefault("Access-Control-Allow-Credentials", "true")
        return response
