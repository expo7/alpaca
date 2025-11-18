from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions

from .tokens import parse_user_id


User = get_user_model()


class JWTAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = authentication.get_authorization_header(request).split()

        if not auth:
            return None
        if auth[0].lower() != self.keyword.lower().encode():
            return None
        if len(auth) == 1:
            raise exceptions.AuthenticationFailed("Invalid Authorization header.")

        token = auth[1].decode()
        user = self._get_user_from_token(token)
        if not user:
            raise exceptions.AuthenticationFailed("Invalid or expired token.")
        return (user, token)

    def _get_user_from_token(self, token):
        user_id = parse_user_id(token)
        if not user_id:
            return None
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
