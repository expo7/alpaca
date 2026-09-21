import hashlib
import hmac

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions


class ResearchOperatorAuthentication(authentication.BaseAuthentication):
    """Authenticate the narrow Daily Trade Research operator API."""

    keyword = "Bearer"

    def authenticate(self, request):
        configured = settings.QUANTELLE_RESEARCH_OPERATOR_TOKEN
        if not configured:
            raise exceptions.AuthenticationFailed("Research operator access is not configured")
        if len(configured) < 32:
            raise exceptions.AuthenticationFailed("Research operator credential is misconfigured")

        header = authentication.get_authorization_header(request).split()
        if len(header) != 2 or header[0].decode().lower() != self.keyword.lower():
            raise exceptions.AuthenticationFailed("Research operator credentials are required")
        try:
            supplied = header[1].decode()
        except UnicodeError as exc:
            raise exceptions.AuthenticationFailed("Invalid research operator credential") from exc

        supplied_digest = hashlib.sha256(supplied.encode()).digest()
        configured_digest = hashlib.sha256(configured.encode()).digest()
        if not hmac.compare_digest(supplied_digest, configured_digest):
            raise exceptions.AuthenticationFailed("Invalid research operator credential")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=settings.QUANTELLE_RESEARCH_OPERATOR_USERNAME,
            defaults={"is_active": True, "is_staff": False, "is_superuser": False},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        elif not user.is_active:
            raise exceptions.AuthenticationFailed("Research operator account is disabled")
        elif user.is_staff or user.is_superuser or user.has_usable_password():
            raise exceptions.AuthenticationFailed("Research operator account is misconfigured")
        return user, "research-operator-token"
