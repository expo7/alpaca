"""Isolated Alpaca Broker sandbox adapter; never selects a production endpoint."""

import os
from urllib.parse import urlencode

import requests
from django.core.cache import cache

AUTH_URL = "https://authx.sandbox.alpaca.markets/v1/oauth2/token"
API_URL = "https://broker-api.sandbox.alpaca.markets"


class BrokerSandboxError(Exception):
    def __init__(self, message, status_code=None, validation_fields=()):
        super().__init__(message)
        self.status_code = status_code
        self.validation_fields = validation_fields


_VALIDATION_FIELD_NAMES = (
    "enabled_assets", "account_type", "contact", "identity", "tax_id", "tax_id_type",
    "disclosures", "agreements", "customer_agreement", "options_agreement", "margin_agreement",
    "documents", "date_of_birth", "phone_number", "postal_code", "risk_tolerance",
    "investment_objective", "investment_time_horizon", "liquidity_needs",
    "annual_income", "total_net_worth", "liquid_net_worth", "investment_experience",
)


def validation_fields(response):
    """Expose only known field names; never return echoed applicant details."""
    try:
        description = str(response.json()).lower()
    except ValueError:
        return []
    return [name for name in _VALIDATION_FIELD_NAMES if name in description]


def configured():
    return bool(os.getenv("ALPACA_BROKER_SANDBOX_API_KEY") and os.getenv("ALPACA_BROKER_SANDBOX_API_SECRET"))


def orders_enabled():
    return os.getenv("ALPACA_BROKER_SANDBOX_ORDER_ENABLED", "false").lower() == "true"


class BrokerSandboxClient:
    def __init__(self, session=None):
        if not configured():
            raise BrokerSandboxError("Broker sandbox credentials are not configured")
        self.session = session or requests.Session()

    def token(self):
        token = cache.get("alpaca_broker_sandbox_access_token")
        if token:
            return token
        response = self.session.post(AUTH_URL, data={
            "grant_type": "client_credentials",
            "client_id": os.environ["ALPACA_BROKER_SANDBOX_API_KEY"],
            "client_secret": os.environ["ALPACA_BROKER_SANDBOX_API_SECRET"],
        }, timeout=12)
        if not response.ok:
            raise BrokerSandboxError(f"Alpaca token request failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise BrokerSandboxError("Alpaca token response was incomplete")
        cache.set("alpaca_broker_sandbox_access_token", token, timeout=max(1, min(int(payload.get("expires_in", 899)) - 60, 840)))
        return token

    def request(self, method, path, *, body=None, params=None):
        if not path.startswith("/v1/") or ".." in path or "?" in path:
            raise BrokerSandboxError("Invalid sandbox API path")
        url = API_URL + path
        if params:
            url += "?" + urlencode(params)
        response = self.session.request(method, url, headers={"Authorization": f"Bearer {self.token()}"}, json=body, timeout=15)
        if response.status_code == 401 and method == "GET":
            cache.delete("alpaca_broker_sandbox_access_token")
            response = self.session.request(method, url, headers={"Authorization": f"Bearer {self.token()}"}, json=body, timeout=15)
        if not response.ok:
            raise BrokerSandboxError(f"Alpaca sandbox request failed ({response.status_code})", response.status_code,
                                     validation_fields(response) if method == "POST" and path == "/v1/accounts" else ())
        return response.json()

    def account(self, account_id):
        return self.request("GET", f"/v1/trading/accounts/{account_id}/account")

    def account_profile(self, account_id):
        return self.request("GET", f"/v1/accounts/{account_id}")

    def create_account(self, application):
        return self.request("POST", "/v1/accounts", body=application)

    def ach_relationships(self, account_id):
        return self.request("GET", f"/v1/accounts/{account_id}/ach_relationships")

    def create_demo_ach_relationship(self, account_id, owner_name, bank_account_number):
        return self.request("POST", f"/v1/accounts/{account_id}/ach_relationships", body={
            "account_owner_name": owner_name, "bank_account_type": "CHECKING",
            "bank_account_number": bank_account_number, "bank_routing_number": "121000358",
            "nickname": "Quantelle sandbox test bank",
        })

    def transfers(self, account_id):
        return self.request("GET", f"/v1/accounts/{account_id}/transfers")

    def demo_deposit(self, account_id, relationship_id):
        return self.request("POST", f"/v1/accounts/{account_id}/transfers", body={
            "transfer_type": "ach", "relationship_id": relationship_id,
            "amount": "1000.00", "direction": "INCOMING", "timing": "immediate",
        })

    def orders(self, account_id):
        return self.request("GET", f"/v1/trading/accounts/{account_id}/orders", params={"status": "all", "limit": 20})

    def cancel_order(self, account_id, order_id):
        response = self.session.delete(
            f"{API_URL}/v1/trading/accounts/{account_id}/orders/{order_id}",
            headers={"Authorization": f"Bearer {self.token()}"}, timeout=15,
        )
        if not response.ok:
            raise BrokerSandboxError(f"Alpaca sandbox cancel failed ({response.status_code})")

    def submit_order(self, account_id, order):
        if not orders_enabled():
            raise BrokerSandboxError("Broker sandbox order submission is disabled")
        return self.request("POST", f"/v1/trading/accounts/{account_id}/orders", body=order)
