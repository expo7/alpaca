"""Paper-only Alpaca OAuth connection. No customer order submission lives here."""

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
        "state": state, "env": "paper",  # Never request a live account or trading scope.
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
    try:
        token_response = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code", "code": code, "client_id": client_id,
            "client_secret": client_secret, "redirect_uri": redirect_uri,
        }, timeout=12)
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        account_response = requests.get(PAPER_ACCOUNT_URL, headers={"Authorization": f"Bearer {token}"}, timeout=12)
        account_response.raise_for_status()
        account_id = account_response.json()["id"]
        if not isinstance(account_id, str) or not account_id:
            raise CustomerPaperError("Alpaca did not identify the paper account")
        connection, _ = CustomerPaperConnection.objects.update_or_create(
            user_id=user_id,
            defaults={"alpaca_account_id": account_id, "encrypted_access_token": cipher.encrypt(token.encode()).decode()},
        )
        return connection
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise CustomerPaperError("Alpaca paper connection could not be verified") from exc
