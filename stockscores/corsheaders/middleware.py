"""Very small CORS middleware stub used for testing."""


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Access-Control-Allow-Origin", "*")
        response.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, PATCH, DELETE")
        response.setdefault("Access-Control-Allow-Headers", "origin, content-type, accept, authorization")
        return response
