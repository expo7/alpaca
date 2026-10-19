"""Paper-only OAuth with explicit trading scope and encrypted token storage."""

import hashlib
import os
import secrets
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.cache import cache

from .models import CustomerPaperConnection


AUTHORIZE_URL = "https://app.alpaca.markets/oauth/authorize"
TOKEN_URL = "https://api.alpaca.markets/oauth/token"
PAPER_ACCOUNT_URL = "https://paper-api.alpaca.markets/v2/account"
STATE_TTL = 600


class CustomerPaperError(RuntimeError):
    pass


def configuration():
    client_id = os.getenv("ALPACA_CONNECT_CLIENT_ID", "")
    client_secret = os.getenv("ALPACA_CONNECT_CLIENT_SECRET", "")
    redirect_uri = os.getenv("ALPACA_CONNECT_REDIRECT_URI", "")
    key = os.getenv("ALPACA_CONNECT_TOKEN_KEY", "")
    enabled = os.getenv("ALPACA_CONNECT_ENABLED", "false").lower() == "true"
    if not (enabled and client_id and client_secret and key and redirect_uri == "https://quantelle.io/api/alpaca-paper/callback/"):
        raise CustomerPaperError("Customer paper connection is not configured")
    try:
        cipher = Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise CustomerPaperError("Customer paper token encryption is not configured") from exc
    return client_id, client_secret, redirect_uri, cipher


def available():
    try:
        configuration()
        return True
    except CustomerPaperError:
        return False


def begin_connection(user):
    client_id, _, redirect_uri, _ = configuration()
    state = secrets.token_urlsafe(32)
    cache.set(f"alpaca-paper-oauth:{hashlib.sha256(state.encode()).hexdigest()}", user.pk, STATE_TTL)
    return AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri,
        "state": state, "env": "paper", "scope": "trading",
    })


def complete_connection(code, state):
    client_id, client_secret, redirect_uri, cipher = configuration()
    if not code or not state or len(state) > 200 or len(code) > 500:
        raise CustomerPaperError("Invalid connection response")
    cache_key = f"alpaca-paper-oauth:{hashlib.sha256(state.encode()).hexdigest()}"
    user_id = cache.get(cache_key)
    if not user_id or not cache.add(f"{cache_key}:used", True, STATE_TTL):
        raise CustomerPaperError("Connection expired or already used")
    cache.delete(cache_key)
    from django.contrib.auth import get_user_model
    from .customer_paper_broker import account_lock, flag, reserved_account_ids
    from .customer_paper_views import can_replace
    user = get_user_model().objects.filter(pk=user_id).first()
    if not user or not user.is_active or not (user.is_superuser or flag("CUSTOMER_PAPER_CUSTOMERS_ENABLED")):
        raise CustomerPaperError("Connection is restricted to administrators")
    try:
        token_response = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code", "code": code, "client_id": client_id,
            "client_secret": client_secret, "redirect_uri": redirect_uri,
        }, timeout=12, allow_redirects=False)
        token_response.raise_for_status()
        token_data = token_response.json()
        token = token_data["access_token"]
        account_response = requests.get(PAPER_ACCOUNT_URL, headers={"Authorization": f"Bearer {token}"}, timeout=12, allow_redirects=False)
        account_response.raise_for_status()
        account = account_response.json()
        account_id = account["id"]
        if not isinstance(account_id, str) or not account_id:
            raise CustomerPaperError("Alpaca did not identify the paper account")
        if account_id in reserved_account_ids() or account.get("status") != "ACTIVE":
            raise CustomerPaperError("Use a separate active customer paper account")
        with account_lock(user_id):
            can_replace(CustomerPaperConnection.objects.filter(user_id=user_id).first())
            previous = CustomerPaperConnection.objects.filter(user_id=user_id).first()
            if previous and previous.alpaca_account_id != account_id and previous.executions.exists():
                raise CustomerPaperError("Reconnect the original paper account to preserve its history")
            connection, _ = CustomerPaperConnection.objects.update_or_create(
                user_id=user_id, defaults={"alpaca_account_id": account_id,
                    "encrypted_access_token": cipher.encrypt(token.encode()).decode(),
                    "auth_method": "oauth", "is_connected": True,
                    "trading_authorized": "trading" in token_data.get("scope", "").split(),
                    "mirror_enabled": False, "consent_at": None, "last_error": ""},
            )
            from .customer_paper_execution import event
            event(connection, "connected", auth_method="oauth")
            return connection
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise CustomerPaperError("Alpaca paper connection could not be verified") from exc
