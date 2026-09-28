"""Staff-only Broker sandbox inspection and tightly scoped manual order trial."""

from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4
from secrets import randbelow

import requests
from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .broker_sandbox import BrokerSandboxClient, BrokerSandboxError, configured, orders_enabled
from .models import TradeSignal
from .broker_sandbox_fixture import synthetic_application

class BrokerAdminPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def account_id_or_none(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError):
        return None


class BrokerSandboxView(APIView):
    permission_classes = [BrokerAdminPermission]

    def get(self, request, account_id=None):
        if not account_id:
            return Response({"configured": configured(), "orders_enabled": orders_enabled(), "environment": "sandbox"})
        account_id = account_id_or_none(account_id)
        if not account_id:
            return Response({"detail": "Invalid account ID"}, status=400)
        try:
            client = BrokerSandboxClient()
            profile = client.account_profile(account_id)
            active = profile.get("status") == "ACTIVE"
            account = client.account(account_id) if active else {}
            orders = client.orders(account_id) if active else []
        except (BrokerSandboxError, requests.RequestException, ValueError):
            return Response({"detail": "Broker sandbox is unavailable"}, status=503)
        return Response({
            "account": {"status": profile.get("status"), "enabled_assets": profile.get("enabled_assets") or [],
                        **{field: account.get(field) for field in ("cash", "buying_power", "trading_blocked", "account_blocked")}},
            "orders": [{field: order.get(field) for field in ("id", "client_order_id", "symbol", "qty", "side", "type", "status", "filled_qty", "filled_avg_price", "limit_price", "time_in_force")}
                       for order in orders[:20]],
            "orders_enabled": orders_enabled(),
        })


class BrokerSandboxOrderView(APIView):
    permission_classes = [BrokerAdminPermission]

    def post(self, request, account_id):
        account_id = account_id_or_none(account_id)
        if not account_id:
            return Response({"detail": "Invalid account ID"}, status=400)
        if not orders_enabled():
            return Response({"detail": "Sandbox order submission is disabled"}, status=403)
        symbol = str(request.data.get("symbol", "")).upper().strip()
        if not symbol.isascii() or not symbol.isalpha() or not 1 <= len(symbol) <= 5:
            return Response({"detail": "Enter a US equity symbol"}, status=400)
        try:
            qty = Decimal(str(request.data.get("qty", "")))
            limit = Decimal(str(request.data.get("limit_price", "")))
        except InvalidOperation:
            return Response({"detail": "Invalid quantity or limit price"}, status=400)
        if qty != 1 or not limit.is_finite() or not Decimal("0.01") <= limit <= Decimal("1000"):
            return Response({"detail": "Trial orders require one share and a valid limit price"}, status=400)
        if request.data.get("confirm") != f"SANDBOX BUY 1 {symbol}":
            return Response({"detail": "Explicit sandbox order confirmation required"}, status=400)
        client_order_id = f"quantelle-admin-sandbox-{uuid4().hex}"
        try:
            client = BrokerSandboxClient()
            account = client.account(account_id)
            if account.get("status") != "ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
                return Response({"detail": "Sandbox account cannot trade"}, status=409)
            if Decimal(str(account.get("non_marginable_buying_power") or "0")) < limit:
                return Response({"detail": "Insufficient sandbox buying power"}, status=409)
            order = client.submit_order(account_id, {
                "symbol": symbol, "qty": "1", "side": "buy", "type": "limit", "limit_price": str(limit),
                "time_in_force": "day", "client_order_id": client_order_id,
            })
        except (BrokerSandboxError, requests.RequestException, ValueError):
            return Response({"detail": "Order outcome unknown; inspect Alpaca orders before retrying", "client_order_id": client_order_id}, status=503)
        return Response({field: order.get(field) for field in ("id", "client_order_id", "symbol", "qty", "status")}, status=status.HTTP_201_CREATED)


class BrokerSandboxCancelOrderView(APIView):
    permission_classes = [BrokerAdminPermission]

    def post(self, request, account_id, order_id):
        if not orders_enabled():
            return Response({"detail": "Sandbox order submission is disabled"}, status=403)
        if request.data.get("confirm") != "CANCEL SANDBOX ORDER":
            return Response({"detail": "Explicit sandbox cancellation confirmation required"}, status=400)
        try:
            client = BrokerSandboxClient()
            orders = client.orders(str(account_id))
            order = next((item for item in orders if item.get("id") == str(order_id)), None)
            if not order or not str(order.get("client_order_id", "")).startswith("quantelle-admin-sandbox-"):
                return Response({"detail": "Quantelle trial order not found"}, status=404)
            if order.get("status") not in ("accepted", "new", "pending_new", "partially_filled", "held", "done_for_day"):
                return Response({"detail": "Order is no longer open; inspect its status"}, status=409)
            client.cancel_order(str(account_id), str(order_id))
        except (BrokerSandboxError, requests.RequestException, ValueError):
            return Response({"detail": "Cancellation outcome unknown; inspect order before retrying"}, status=503)
        return Response({"detail": "Cancellation requested; inspect order to confirm its final status"}, status=202)


class BrokerSandboxMirrorPreviewView(APIView):
    """Read-only comparison of a published option setup with one sandbox account."""
    permission_classes = [BrokerAdminPermission]

    def get(self, request, account_id):
        signal = (TradeSignal.objects.filter(
            is_test=False, instrument_type__in=("call", "put"),
            status__in=(TradeSignal.STATUS_PUBLISHED, TradeSignal.STATUS_OPEN),
            paper_execution_enabled=True,
        ).order_by("-published_at", "-created_at").first())
        if signal is None:
            return Response({"detail": "No active published option setup", "can_mirror": False})
        try:
            client = BrokerSandboxClient()
            profile = client.account_profile(str(account_id))
            account = client.account(str(account_id))
        except (BrokerSandboxError, requests.RequestException, ValueError):
            return Response({"detail": "Broker sandbox is unavailable"}, status=503)

        enabled_assets = profile.get("enabled_assets") or []
        approved = account.get("options_approved_level") or 0
        trading = account.get("options_trading_level") or 0
        premium = signal.actual_entry if signal.status == TradeSignal.STATUS_OPEN else signal.entry_high or signal.entry_low
        cost = premium * 100  # One standard option contract; planning estimate only.
        option_bp = account.get("options_buying_power")
        checks = {
            "options_asset_enabled": "us_option" in enabled_assets,
            "level_2_approved": int(approved) >= 2 and int(trading) >= 2,
            "account_active": profile.get("status") == "ACTIVE" and not account.get("trading_blocked"),
            "estimated_buying_power": option_bp is not None and Decimal(str(option_bp)) >= cost,
        }
        return Response({
            "can_mirror": False, "mode": "read_only_preview", "checks": checks,
            "signal": {"id": signal.pk, "status": signal.status, "contract": signal.contract_symbol,
                       "paper_order_status": signal.paper_order_status, "one_contract_estimate": str(cost)},
            "account": {"enabled_assets": enabled_assets, "options_approved_level": approved,
                        "options_trading_level": trading, "options_buying_power": option_bp},
            "detail": "Preview only. No Broker option order is submitted or scheduled.",
        })


class BrokerSandboxOptionsAccessView(APIView):
    """Read-only probe of the partner's options approval entitlement in sandbox."""
    permission_classes = [BrokerAdminPermission]

    def get(self, request, account_id):
        try:
            client = BrokerSandboxClient()
            profile = client.account_profile(str(account_id))
            account = client.account(str(account_id)) if profile.get("status") == "ACTIVE" else {}
            try:
                approvals = client.options_approvals(str(account_id))
                access = "available"
            except BrokerSandboxError as exc:
                if exc.status_code == 403:
                    access, approvals = "not_enabled_or_account_inaccessible", None
                else:
                    raise
        except (BrokerSandboxError, requests.RequestException, ValueError):
            return Response({"detail": "Options access check unavailable"}, status=503)
        return Response({
            "partner_options_access": access,
            "account_status": profile.get("status"),
            "enabled_assets": profile.get("enabled_assets") or [],
            "options_approved_level": account.get("options_approved_level"),
            "options_trading_level": account.get("options_trading_level"),
            "approval_requests": [{"requested_level": item.get("requested_level"), "status": item.get("status"),
                                   "approved_level": item.get("approved_level")} for item in
                                  (approvals.get("approvals", []) if isinstance(approvals, dict) else approvals or [])],
        })


class BrokerSandboxCreateAccountView(APIView):
    """Create only a fictional applicant in the fixed Broker sandbox environment."""
    permission_classes = [BrokerAdminPermission]

    def post(self, request):
        options = request.data.get("options")
        if type(options) is not bool or request.data.get("confirm") != "CREATE SYNTHETIC SANDBOX ACCOUNT":
            return Response({"detail": "Choose assets and confirm synthetic sandbox creation"}, status=400)
        throttle_key = f"broker_sandbox_create_{request.user.pk}"
        if not cache.add(throttle_key, True, timeout=60):
            return Response({"detail": "Wait one minute and inspect Alpaca before another application"}, status=429)
        try:
            result = BrokerSandboxClient().create_account(synthetic_application(options=options))
        except BrokerSandboxError as exc:
            return Response({"detail": f"Alpaca sandbox rejected or could not confirm the application (HTTP {exc.status_code or 'unknown'}). Inspect Alpaca accounts before retrying.",
                             "validation_fields": exc.validation_fields}, status=502)
        except (requests.RequestException, ValueError):
            return Response({"detail": "Application outcome unknown; inspect Alpaca accounts before retrying"}, status=503)
        return Response({
            "id": result.get("id"), "account_number": result.get("account_number"),
            "status": result.get("status"), "enabled_assets": result.get("enabled_assets"),
            "synthetic": True, "environment": "sandbox",
        }, status=201)


class BrokerSandboxFundingView(APIView):
    """Inspect or advance the fixed virtual ACH demo for one synthetic account."""
    permission_classes = [BrokerAdminPermission]
    TARGET = Decimal("25000.00")

    def get(self, request, account_id):
        try:
            client = BrokerSandboxClient()
            relationships = client.ach_relationships(str(account_id))
            transfers = client.transfers(str(account_id))
        except (BrokerSandboxError, requests.RequestException, ValueError):
            return Response({"detail": "Broker sandbox funding status unavailable"}, status=503)
        return Response({
            "relationships": [{"id": item.get("id"), "status": item.get("status"), "nickname": item.get("nickname")}
                              for item in relationships],
            "transfers": [{"id": item.get("id"), "status": item.get("status"), "amount": item.get("amount"),
                           "direction": item.get("direction")} for item in transfers[:10]],
        })

    def post(self, request, account_id):
        if request.data.get("confirm") != "FUND SYNTHETIC SANDBOX ACCOUNT":
            return Response({"detail": "Explicit virtual funding confirmation required"}, status=400)
        throttle_key = f"broker_sandbox_funding_{account_id}"
        if not cache.add(throttle_key, True, timeout=60):
            return Response({"detail": "Wait one minute and inspect funding before retrying"}, status=429)
        try:
            client = BrokerSandboxClient()
            profile = client.account_profile(str(account_id))
            if profile.get("status") != "ACTIVE" or not str(profile.get("contact", {}).get("email_address", "")).endswith("@example.com"):
                return Response({"detail": "Only active synthetic sandbox accounts can use demo funding"}, status=409)
            relationships = client.ach_relationships(str(account_id))
            approved = next((item for item in relationships if item.get("status") == "APPROVED" and
                             item.get("nickname") == "Quantelle sandbox test bank"), None)
            if not approved:
                if relationships:
                    return Response({"detail": "ACH relationship is pending or belongs to another workflow; inspect funding before retrying"}, status=409)
                identity = profile.get("identity") or {}
                owner = " ".join(filter(None, (identity.get("given_name"), identity.get("family_name"))))
                if not owner:
                    return Response({"detail": "Synthetic account identity unavailable"}, status=409)
                relationship = client.create_demo_ach_relationship(str(account_id), owner, f"{randbelow(10**10):010d}")
                return Response({"step": "relationship", "status": relationship.get("status"),
                                 "detail": "Virtual bank link requested. Inspect funding for APPROVED, then fund."}, status=202)
            transfers = client.transfers(str(account_id))
            incoming = [item for item in transfers if item.get("direction") == "INCOMING" and
                        item.get("status") not in ("CANCELED", "CANCELLED", "REJECTED", "FAILED", "RETURNED")]
            if any(item.get("status") not in ("COMPLETE", "COMPLETED", "SETTLED") for item in incoming):
                return Response({"detail": "An incoming deposit is still processing; inspect it before adding funds"}, status=409)
            existing = sum((Decimal(str(item["amount"])) for item in incoming), Decimal("0"))
            remaining = self.TARGET - existing
            if remaining <= 0:
                return Response({"detail": "The $25,000 demo funding target has been reached"}, status=409)
            result = client.demo_deposit(str(account_id), approved["id"], f"{remaining:.2f}")
            return Response({"step": "deposit", "id": result.get("id"), "status": result.get("status"),
                             "detail": f"Virtual ${remaining:,.2f} deposit requested toward $25,000. Inspect funding and account balance."}, status=202)
        except (BrokerSandboxError, requests.RequestException, ValueError, KeyError, InvalidOperation):
            return Response({"detail": "Funding outcome unknown; inspect Alpaca and funding status before retrying"}, status=503)
