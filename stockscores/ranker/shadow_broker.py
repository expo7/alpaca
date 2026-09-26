"""Dedicated paper account client. Never reads primary keys for an order request."""

import os
import requests
from decimal import Decimal

from .alpaca_paper import PaperTradingError, AlpacaPaperClient

from .alpaca_paper import PAPER_API_URL


class ShadowIdentityError(RuntimeError):
    pass


def execution_configured():
    return (os.getenv("SHADOW_TRADING_ENABLED", "false").lower() == "true" and
            os.getenv("SHADOW_EXECUTION_CONFIRMED", "false").lower() == "true" and
            os.getenv("SHADOW_EMERGENCY_PAUSE", "true").lower() == "false")


def verify_account_identity(get=requests.get, *, require_enabled=True):
    """Explicitly identify both paper accounts, with no order submission."""
    if require_enabled and not execution_configured():
        raise ShadowIdentityError("Shadow execution is disabled or paused")
    if os.getenv("SHADOW_ALPACA_PAPER_BASE_URL") != PAPER_API_URL or os.getenv("ALPACA_PAPER_BASE_URL", PAPER_API_URL) != PAPER_API_URL:
        raise ShadowIdentityError("Both endpoints must be the exact Alpaca paper endpoint")
    shadow = (os.getenv("SHADOW_ALPACA_PAPER_API_KEY"), os.getenv("SHADOW_ALPACA_PAPER_SECRET_KEY"))
    primary = (os.getenv("ALPACA_PAPER_API_KEY"), os.getenv("ALPACA_PAPER_SECRET_KEY"))
    if not all(shadow + primary):
        raise ShadowIdentityError("Both sets of paper credentials are required")

    def identify(keys):
        try:
            response = get(f"{PAPER_API_URL}/v2/account", headers={
                "APCA-API-KEY-ID": keys[0], "APCA-API-SECRET-KEY": keys[1],
            }, timeout=12)
            response.raise_for_status()
            identifier = response.json().get("id")
        except (requests.RequestException, ValueError, AttributeError) as exc:
            raise ShadowIdentityError("Paper account identity could not be verified") from exc
        if not isinstance(identifier, str) or not identifier.strip():
            raise ShadowIdentityError("Paper account response has no account ID")
        return identifier

    shadow_id, primary_id = identify(shadow), identify(primary)
    if shadow_id == primary_id:
        raise ShadowIdentityError("Shadow and primary paper account IDs match")
    return shadow_id


def _configure_shadow_client(client):
    """Never invoke the base constructor: it reads primary credentials."""
    client.base_url = os.getenv("SHADOW_ALPACA_PAPER_BASE_URL", "")
    if client.base_url != PAPER_API_URL:
        raise ShadowIdentityError("Shadow broker endpoint is not the exact paper endpoint")
    key = os.getenv("SHADOW_ALPACA_PAPER_API_KEY", "")
    secret = os.getenv("SHADOW_ALPACA_PAPER_SECRET_KEY", "")
    if not key or not secret:
        raise ShadowIdentityError("Shadow paper credentials are absent")
    client.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    client.data_url = "https://data.alpaca.markets"
    client.config = type("ShadowQuoteConfig", (), {
        "stock_feed": os.getenv("SHADOW_ALPACA_STOCK_FEED", "iex"),
        "option_feed": os.getenv("SHADOW_ALPACA_OPTION_FEED", "indicative"),
        "max_quote_age_seconds": min(max(int(os.getenv("SHADOW_MAX_QUOTE_AGE_SECONDS", "20")), 1), 30),
    })()


class ShadowMarketDataClient:
    """Market data only; no order or position methods exist on this type."""

    _request = AlpacaPaperClient._request
    _require_fresh_quote = AlpacaPaperClient._require_fresh_quote
    clock = AlpacaPaperClient.clock
    stock_quote = AlpacaPaperClient.stock_quote
    option_quote = AlpacaPaperClient.option_quote

    def __init__(self):
        _configure_shadow_client(self)


class ShadowPaperClient(AlpacaPaperClient):
    """Explicit shadow-only order client, forbidden unless all execution gates pass."""

    def __init__(self):
        if not execution_configured():
            raise ShadowIdentityError("Shadow execution is disabled or paused")
        _configure_shadow_client(self)

    def by_client_id(self, client_id):
        return self._request("GET", f"{self.base_url}/v2/orders:by_client_order_id", params={"client_order_id": client_id})
