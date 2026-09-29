"""Exact-paper authenticated REST transport with shared, credential-free budgets."""
import hashlib
import json
import os
import time
from contextlib import contextmanager
from decimal import Decimal
from urllib.parse import urlparse

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.core.cache import cache
from django.db import connection as database

from .alpaca_paper import AlpacaPaperClient, PAPER_API_URL, PaperTradingError, load_paper_config


class CustomerBrokerError(PaperTradingError):
    def __init__(self, message, *, code=None):
        super().__init__(message)
        self.code = code


def flag(name):
    return os.getenv(name, "false").lower() == "true"


def cipher():
    try:
        return Fernet(os.environ["CUSTOMER_PAPER_CREDENTIAL_KEY"].encode())
    except (KeyError, ValueError, TypeError) as exc:
        raise CustomerBrokerError("Paper credential storage is not configured.") from exc


def credentials_ready():
    try:
        cipher()
        return flag("CUSTOMER_PAPER_CONNECT_ENABLED")
    except CustomerBrokerError:
        return False


def execution_enabled():
    return flag("CUSTOMER_PAPER_EXECUTION_ENABLED") and credentials_ready()


def encrypt_credentials(key, secret):
    return cipher().encrypt(json.dumps({"key": key, "secret": secret}).encode()).decode()


def _consume(key, limit, period=60):
    bucket = int(time.time() // period)
    name = f"customer-paper-budget:{key}:{bucket}:{period}"
    cache.add(name, 0, timeout=period * 2)
    try:
        count = cache.incr(name)
    except ValueError as exc:
        raise CustomerBrokerError("Paper request budget is unavailable.") from exc
    if count > limit:
        raise CustomerBrokerError("Paper request budget reached. Try again shortly.", code=429)


def reserve_request(account):
    """80/minute avoids fixed-window bursts reaching Alpaca's 200/minute."""
    if cache.get(f"customer-paper-backoff:{account}") or cache.get("customer-paper-global-backoff"):
        raise CustomerBrokerError("Alpaca asked us to pause requests. Try again shortly.", code=429)
    _consume("server", 300)
    _consume(account, 80)
    _consume(account, 12, period=1)


@contextmanager
def account_lock(identity):
    """Session advisory lock: no lease expiry while an HTTP call is in flight."""
    key = int.from_bytes(hashlib.sha256(f"customer-paper:{identity}".encode()).digest()[:8], "big", signed=True)
    cache_key = f"customer-paper-lock:{identity}"
    postgres = database.vendor == "postgresql"
    if postgres:
        with database.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
            acquired = cursor.fetchone()[0]
    else:
        acquired = cache.add(cache_key, True, timeout=180)
    if not acquired:
        raise CustomerBrokerError("This paper account is already being updated. Try again shortly.", code=409)
    try:
        yield
    finally:
        if postgres:
            with database.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [key])
        else:
            cache.delete(cache_key)


class CustomerPaperClient(AlpacaPaperClient):
    """Reuse order payloads, but never the house credentials or data endpoint."""
    def __init__(self, connection=None, *, key=None, secret=None):
        self.config = load_paper_config()
        self.base_url = PAPER_API_URL
        self.data_url = None
        if connection is not None:
            try:
                if connection.auth_method == "api_key":
                    stored = json.loads(cipher().decrypt(connection.encrypted_access_token.encode()))
                    key, secret = stored["key"], stored["secret"]
                    self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
                else:
                    token = Fernet(os.environ["ALPACA_CONNECT_TOKEN_KEY"].encode()).decrypt(connection.encrypted_access_token.encode()).decode()
                    self.headers = {"Authorization": f"Bearer {token}"}
            except (InvalidToken, KeyError, ValueError, TypeError) as exc:
                raise CustomerBrokerError("Stored paper authorization needs reconnecting.") from exc
            self.identity = connection.alpaca_account_id
        else:
            if not key or not secret:
                raise CustomerBrokerError("Enter both paper API credentials.")
            self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
            self.identity = hashlib.sha256(key.encode()).hexdigest()

    def _request(self, method, url, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "paper-api.alpaca.markets" or not parsed.path.startswith("/v2/"):
            raise CustomerBrokerError("Refusing a request outside the paper Trading API.")
        reserve_request(self.identity)
        try:
            response = requests.request(method, url, headers=self.headers, timeout=8, allow_redirects=False, **kwargs)
            code = response.status_code
            if code == 429:
                try:
                    delay = min(300, max(60, int(response.headers.get("Retry-After", 60))))
                except (ValueError, TypeError):
                    delay = 60
                cache.set(f"customer-paper-backoff:{self.identity}", True, delay)
                # Conservative shared cooldown also protects against an IP-wide throttle.
                cache.set("customer-paper-global-backoff", True, delay)
            if code >= 300:
                raise CustomerBrokerError(f"Alpaca paper request returned HTTP {code}.", code=code)
            if code == 204:
                return {}
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            # Never include request headers, provider error bodies, or secret values.
            raise CustomerBrokerError("Alpaca paper response could not be confirmed. Refresh before retrying.") from exc

    def account(self):
        return self._request("GET", f"{self.base_url}/v2/account")

    def find_order(self, client_id):
        try:
            return self._request("GET", f"{self.base_url}/v2/orders:by_client_order_id", params={"client_order_id": client_id})
        except CustomerBrokerError as exc:
            if exc.code == 404:
                return None
            raise


def reserved_account_ids():
    """Fail closed if configured house/shadow identities cannot be established."""
    cached = cache.get("customer-paper-reserved-identities")
    if cached is not None:
        return cached
    result = []
    for prefix in ("ALPACA_PAPER", "SHADOW_ALPACA_PAPER"):
        key, secret = os.getenv(prefix + "_API_KEY"), os.getenv(prefix + "_SECRET_KEY")
        if key or secret:
            account = CustomerPaperClient(key=key, secret=secret).account()
            if not account.get("id"):
                raise CustomerBrokerError("Could not verify internal paper account identities.")
            result.append(account["id"])
    cache.set("customer-paper-reserved-identities", result, 60)
    return result


def verify_customer_account(client):
    account = client.account()
    identity = account.get("id")
    if not isinstance(identity, str) or not identity or len(identity) > 80:
        raise CustomerBrokerError("Alpaca did not identify a paper account.")
    if identity in reserved_account_ids():
        raise CustomerBrokerError("Use a separate customer paper account; this is an internal execution account.")
    if account.get("status") != "ACTIVE":
        raise CustomerBrokerError("The paper account is not active yet.")
    return account


def shared_option_quote(symbol):
    # One short-lived quote cache, no per-customer market-data streams.
    key = f"customer-paper-quote:{symbol}"
    quote = cache.get(key)
    if quote is None:
        try:
            quote = AlpacaPaperClient().option_quote(symbol)
        except (PaperTradingError, requests.RequestException, KeyError, ValueError) as exc:
            raise CustomerBrokerError("A fresh shared options quote is unavailable. Try again shortly.") from exc
        cache.set(key, quote, 3)
    return quote
