from django.conf import settings
from django.core.cache import cache

YF_HIT_COUNTER_KEY = "ranker:yfinance:hits"


def increment_yf_counter() -> None:
    """Increment the yfinance hit counter when in development/debug mode."""
    if not getattr(settings, "DEBUG", False):
        return
    try:
        cache.incr(YF_HIT_COUNTER_KEY)
    except Exception:
        cache.set(YF_HIT_COUNTER_KEY, 1, None)


def get_yf_counter() -> int:
    """Return the tracked yfinance hit count (0 if disabled or missing)."""
    if not getattr(settings, "DEBUG", False):
        return 0
    return int(cache.get(YF_HIT_COUNTER_KEY, 0) or 0)
