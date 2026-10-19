import hashlib
import hmac
from urllib.parse import urlparse

from django.conf import settings
from django.db import DatabaseError
from rest_framework.throttling import SimpleRateThrottle

from .models import AnalyticsEvent


BOT_MARKERS = (
    "bot",
    "crawler",
    "spider",
    "slurp",
    "headless",
    "semrush",
    "ahrefs",
    "facebookexternalhit",
    "python-requests",
    "curl/",
    "wget/",
)

ALLOWED_EVENTS = {
    "page_view",
    "dashboard_view",
    "article_view",
    "chart_opened",
    "explanation_opened",
    "watchlist_add",
    "ranking_run",
    "registration",
}


class AnalyticsEventThrottle(SimpleRateThrottle):
    rate = "120/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": "analytics",
            "ident": self.get_ident(request),
        }


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _visitor_hash(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
    identity = f"{_client_ip(request)}|{user_agent}".encode()
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, identity, hashlib.sha256).hexdigest()


def _is_bot(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
    return not user_agent or any(marker in user_agent for marker in BOT_MARKERS)


def _device_type(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
    if any(marker in user_agent for marker in ("ipad", "tablet")):
        return "tablet"
    if any(marker in user_agent for marker in ("mobile", "android", "iphone")):
        return "mobile"
    return "desktop"


def _referrer_host(value):
    try:
        return (urlparse(value or "").hostname or "")[:255]
    except ValueError:
        return ""


def record_analytics_event(request, event_name, *, path="", metadata=None):
    """Record a vetted analytics event; silently ignore bots and invalid names."""
    event_name = str(event_name or "").strip().lower()[:64]
    if event_name not in ALLOWED_EVENTS or _is_bot(request):
        return None

    clean_path = str(path or "").strip()[:512]
    if clean_path and not clean_path.startswith("/"):
        clean_path = ""

    safe_metadata = metadata if isinstance(metadata, dict) else {}
    safe_metadata = {
        str(key)[:64]: value
        for key, value in list(safe_metadata.items())[:10]
        if isinstance(value, (str, int, float, bool)) or value is None
    }

    try:
        return AnalyticsEvent.objects.create(
            event_name=event_name,
            path=clean_path,
            referrer_host=_referrer_host(request.data.get("referrer", "") if hasattr(request, "data") else ""),
            visitor_hash=_visitor_hash(request),
            device_type=_device_type(request),
            user=request.user if request.user.is_authenticated else None,
            metadata=safe_metadata,
        )
    except DatabaseError:
        # Analytics must never prevent registration, ranking, or page delivery.
        return None
