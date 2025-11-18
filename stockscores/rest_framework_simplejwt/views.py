from rest_framework.response import Response
from rest_framework.views import APIView


class TokenObtainPairView(APIView):
    def post(self, request, *args, **kwargs):
        return Response({"detail": "Token issuance not available in test stub."}, status=501)


class TokenRefreshView(APIView):
    def post(self, request, *args, **kwargs):
        return Response({"detail": "Token refresh not available in test stub."}, status=501)
