from decimal import Decimal, InvalidOperation

from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .customer_paper import CustomerPaperError, available, begin_connection, complete_connection
from .customer_paper_broker import (
    CustomerBrokerError, CustomerPaperClient, account_lock, credentials_ready,
    encrypt_credentials, execution_enabled, flag, verify_customer_account,
)
from .customer_paper_execution import ACTIVE, create_execution, event, preview, verified_account, worker_ready
from .models import CustomerPaperConnection, TradeSignal


class StaffPaperPermission(permissions.BasePermission):
    """Private admin preview; explicit server switch opens the same own-account API."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            request.user.is_superuser or flag("CUSTOMER_PAPER_CUSTOMERS_ENABLED")))


def response(data, status=200):
    return Response(data, status=status, headers={"Cache-Control": "private, no-store"})


def error_response(exc):
    code = getattr(exc, "code", None)
    return response({"detail": str(exc)}, code if code in (409, 429) else 400)


def active_connection(user):
    record = CustomerPaperConnection.objects.filter(user=user, is_connected=True).first()
    if not record:
        raise CustomerBrokerError("Connect your paper account first.")
    return record


def can_replace(record):
    if record and record.executions.exclude(state__in=("closed", "closed_external", "canceled", "rejected")).exists():
        raise CustomerBrokerError("Pause mirroring and finish or reconcile existing customer orders before disconnecting or replacing credentials.", code=409)


def summary(user):
    record = CustomerPaperConnection.objects.filter(user=user).first()
    connected = bool(record and record.is_connected)
    return {
        "available": credentials_ready(), "oauth_available": available(),
        "customer_rollout": flag("CUSTOMER_PAPER_CUSTOMERS_ENABLED"),
        "connected": connected, "account_suffix": record.alpaca_account_id[-4:] if connected else None,
        "auth_method": record.auth_method if connected else None,
        "trading_authorized": bool(connected and record.trading_authorized),
        "execution_enabled": execution_enabled(), "executor_ready": worker_ready(), "mirror_enabled": bool(connected and record.mirror_enabled),
        "max_trade_notional": str(record.max_trade_notional) if record else "1000.00",
        "max_open_positions": record.max_open_positions if record else 2,
        "last_checked_at": record.last_checked_at if record else None,
        "last_error": record.last_error if connected else "",
        "environment": "paper", "quantity": 1,
    }


class CustomerPaperConnectionView(APIView):
    permission_classes = [StaffPaperPermission]

    def get(self, request):
        return response(summary(request.user))

    def post(self, request):
        if not credentials_ready():
            return response({"detail": "Paper credential storage is not configured."}, 503)
        key, secret = request.data.get("api_key"), request.data.get("api_secret")
        if not all(isinstance(v, str) and 10 <= len(v) <= 200 and not any(c.isspace() for c in v) for v in (key, secret)):
            return response({"detail": "Paste the paper API key and secret without spaces or quotes."}, 400)
        try:
            with account_lock(request.user.pk):
                previous = CustomerPaperConnection.objects.filter(user=request.user).first()
                can_replace(previous)
                client = CustomerPaperClient(key=key, secret=secret)
                account = verify_customer_account(client)
                if previous and previous.alpaca_account_id != account["id"] and previous.executions.exists():
                    raise CustomerBrokerError("This login has trade history for a different paper account. Reconnect the same account to preserve its history.", code=409)
                record, _ = CustomerPaperConnection.objects.update_or_create(user=request.user, defaults={
                    "alpaca_account_id": account["id"], "encrypted_access_token": encrypt_credentials(key, secret),
                    "auth_method": "api_key", "is_connected": True, "trading_authorized": True,
                    "mirror_enabled": False, "consent_at": None, "last_error": "", "last_checked_at": timezone.now(),
                })
                event(record, "connected", auth_method="api_key")
                return response(summary(request.user), 201)
        except CustomerBrokerError as exc:
            return error_response(exc)
        except IntegrityError:
            return response({"detail": "This paper account is already linked to another Quantelle account."}, 409)

    def patch(self, request):
        try:
            with account_lock(request.user.pk):
                record = active_connection(request.user)
                allowed = {"mirror_enabled", "max_trade_notional", "max_open_positions", "consent"}
                if set(request.data) - allowed:
                    raise CustomerBrokerError("Unknown paper setting.")
                if "max_trade_notional" in request.data:
                    try:
                        budget = Decimal(str(request.data["max_trade_notional"]))
                        if not budget.is_finite() or not 1 <= budget <= 100000:
                            raise ValueError
                        record.max_trade_notional = budget.quantize(Decimal("0.01"))
                    except (ValueError, InvalidOperation):
                        raise CustomerBrokerError("Trade budget must be between $1 and $100,000.")
                if "max_open_positions" in request.data:
                    value = request.data["max_open_positions"]
                    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 10:
                        raise CustomerBrokerError("Position limit must be an integer from 1 to 10.")
                    record.max_open_positions = value
                if "mirror_enabled" in request.data:
                    value = request.data["mirror_enabled"]
                    if not isinstance(value, bool):
                        raise CustomerBrokerError("Mirroring must be true or false.")
                    if value and not record.mirror_enabled:
                        if not execution_enabled() or not record.trading_authorized:
                            raise CustomerBrokerError("Paper execution is disabled or requires reconnecting with trading permission.")
                        if request.data.get("consent") is not True:
                            raise CustomerBrokerError("Confirm automatic paper entries and ongoing exit management.")
                        record.consent_at = timezone.now()
                    record.mirror_enabled = value
                record.save()
                event(record, "settings_updated", mirror_enabled=record.mirror_enabled,
                      max_trade_notional=str(record.max_trade_notional), max_open_positions=record.max_open_positions)
                return response(summary(request.user))
        except CustomerBrokerError as exc:
            return error_response(exc)

    def delete(self, request):
        try:
            with account_lock(request.user.pk):
                record = CustomerPaperConnection.objects.filter(user=request.user).first()
                can_replace(record)
                if record:
                    # Preserve audit history, remove usable credentials.
                    record.encrypted_access_token = ""
                    record.is_connected = record.mirror_enabled = record.trading_authorized = False
                    record.save()
                    event(record, "disconnected")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CustomerBrokerError as exc:
            return error_response(exc)


class CustomerPaperAccountView(APIView):
    permission_classes = [StaffPaperPermission]

    def get(self, request):
        try:
            with account_lock(request.user.pk):
                record = active_connection(request.user)
                client = CustomerPaperClient(record)
                account = verified_account(record, client)
                positions = client.positions()
                orders = client._request("GET", f"{client.base_url}/v2/orders", params={"status": "open", "limit": 500})
                record.last_checked_at = timezone.now()
                record.last_error = ""
                record.save(update_fields=["last_checked_at", "last_error", "updated_at"])
                data = {"account": {k: account.get(k) for k in ("status", "cash", "buying_power", "options_buying_power", "equity", "options_trading_level", "trading_blocked")},
                        "positions": [{k: p.get(k) for k in ("symbol", "qty", "side", "avg_entry_price", "unrealized_pl")} for p in positions],
                        "orders": [{k: o.get(k) for k in ("id", "symbol", "qty", "filled_qty", "side", "status", "type", "limit_price", "stop_price")} for o in orders],
                        "checked_at": record.last_checked_at, "environment": "paper"}
                return response(data)
        except CustomerBrokerError as exc:
            return error_response(exc)


class CustomerPaperExecutionsView(APIView):
    permission_classes = [StaffPaperPermission]

    def get(self, request):
        record = CustomerPaperConnection.objects.filter(user=request.user).first()
        rows = record.executions.order_by("-created_at")[:50] if record else []
        events = record.events.order_by("-created_at", "-pk")[:50] if record else []
        return response({"executions": [{k: getattr(row, k) for k in (
            "id", "signal_id", "source", "state", "symbol", "quantity", "entry_limit", "stop", "target", "filled_quantity", "entry_fill", "exit_fill", "order_status", "last_error", "checked_at", "created_at")} for row in rows],
            "events": [{"kind": e.kind, "details": e.details, "created_at": e.created_at} for e in events]})

    def post(self, request):
        try:
            signal_id = request.data.get("signal_id")
            if not isinstance(signal_id, int) or isinstance(signal_id, bool):
                raise CustomerBrokerError("Select a published signal.")
            signals = TradeSignal.objects.all()
            if not (request.user.is_staff or request.user.is_superuser):
                signals = signals.filter(is_test=False)
            signal = signals.get(pk=signal_id)
            with account_lock(request.user.pk):
                record = active_connection(request.user)
                if request.data.get("action") == "preview":
                    return response(preview(record, signal))
                if request.data.get("action") != "submit" or request.data.get("confirm_paper") is not True:
                    raise CustomerBrokerError("Preview and confirm the one-contract paper trade first.")
                row = create_execution(record, signal)
                return response({"execution_id": row.pk, "state": row.state}, 201)
        except TradeSignal.DoesNotExist:
            return response({"detail": "Signal not found."}, 404)
        except CustomerBrokerError as exc:
            return error_response(exc)
        except IntegrityError:
            return response({"detail": "An execution already exists for this signal."}, 409)
        except (KeyError, ValueError):
            return response({"detail": "The paper trade could not be evaluated. Refresh the account."}, 400)


class CustomerPaperConnectView(APIView):
    permission_classes = [StaffPaperPermission]

    def post(self, request):
        try:
            with account_lock(request.user.pk):
                can_replace(CustomerPaperConnection.objects.filter(user=request.user).first())
                url = begin_connection(request.user)
        except CustomerPaperError:
            return response({"detail": "OAuth connection is not configured. Use paper API credentials in the meantime."}, 503)
        except CustomerBrokerError as exc:
            return error_response(exc)
        return response({"authorize_url": url})


class CustomerPaperCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            complete_connection(request.query_params.get("code"), request.query_params.get("state"))
        except (CustomerPaperError, CustomerBrokerError, IntegrityError):
            return HttpResponseRedirect("/signals?alpaca=connection-failed")
        return HttpResponseRedirect("/signals?alpaca=connected")
