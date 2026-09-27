"""Staff-only Broker sandbox inspection and tightly scoped manual order trial."""

from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

import requests
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .broker_sandbox import BrokerSandboxClient, BrokerSandboxError, configured, orders_enabled

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
            account = client.account(account_id)
            orders = client.orders(account_id)
        except (BrokerSandboxError, requests.RequestException, ValueError):
            return Response({"detail": "Broker sandbox is unavailable"}, status=503)
        return Response({
            "account": {field: account.get(field) for field in ("status", "cash", "buying_power", "trading_blocked", "account_blocked")},
            "orders": [{field: order.get(field) for field in ("id", "client_order_id", "symbol", "qty", "side", "type", "status", "filled_qty")}
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
