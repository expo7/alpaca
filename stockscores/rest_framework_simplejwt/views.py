from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .tokens import RefreshToken, AccessToken, parse_user_id


class TokenObtainPairView(APIView):
    """
    Lightweight stand-in for the SimpleJWT login view. It checks credentials
    using Django's authenticate and returns opaque access/refresh strings.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        if not username or not password:
            return Response(
                {"detail": "Username and password required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request=request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "No active account found with the given credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "username": user.get_username(),
            }
        )


class TokenRefreshView(APIView):
    """
    Minimal refresh endpoint. Since we do not persist refresh tokens in this
    stub, we just parse out the embedded user id and mint a new access token.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        refresh_value = request.data.get("refresh")
        user_id = parse_user_id(refresh_value)
        if not user_id:
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = AccessToken(user_id=user_id)
        return Response({"access": str(token), "username": user.get_username()})
