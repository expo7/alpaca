from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from paper.api.views import OrderViewSet, PositionViewSet
from paper.models import (
    PaperPortfolio,
    PaperOrder,
    PaperTrade,
    PaperPosition,
)


User = get_user_model()


class AuditApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="audit-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Audit",
            base_currency="USD",
            status="active",
        )
        self.factory = APIRequestFactory()

    def test_order_audit_returns_events_and_trades(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="market",
            tif="day",
            quantity=Decimal("10"),
            filled_quantity=Decimal("10"),
            average_fill_price=Decimal("150"),
            status="filled",
            notes={"events": [{"event": "fill", "timestamp": "2024-01-01T00:00:00Z"}]},
        )
        PaperTrade.objects.create(
            order=order,
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            quantity=Decimal("10"),
            price=Decimal("150"),
            fees=Decimal("0"),
            slippage=Decimal("0"),
            realized_pnl=Decimal("0"),
        )
        view = OrderViewSet.as_view({"get": "audit"})
        req = self.factory.get(f"/api/paper/orders/{order.id}/audit/")
        force_authenticate(req, user=self.user)
        resp = view(req, pk=order.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("events", resp.data)
        self.assertEqual(len(resp.data["events"]), 1)
        self.assertIn("trades", resp.data)
        self.assertEqual(len(resp.data["trades"]), 1)

    def test_position_audit_returns_trades_and_orders(self):
        position = PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            quantity=Decimal("5"),
            avg_price=Decimal("100"),
            market_value=Decimal("500"),
            unrealized_pnl=Decimal("0"),
        )
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="sell",
            order_type="limit",
            tif="day",
            quantity=Decimal("5"),
            limit_price=Decimal("110"),
            status="new",
        )
        PaperTrade.objects.create(
            order=order,
            portfolio=self.portfolio,
            symbol="MSFT",
            side="sell",
            quantity=Decimal("1"),
            price=Decimal("110"),
            fees=Decimal("0"),
            slippage=Decimal("0"),
            realized_pnl=Decimal("10"),
        )
        view = PositionViewSet.as_view({"get": "audit"})
        req = self.factory.get(f"/api/paper/positions/{position.id}/audit/")
        force_authenticate(req, user=self.user)
        resp = view(req, pk=position.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("orders", resp.data)
        self.assertGreaterEqual(len(resp.data["orders"]), 1)
        self.assertIn("trades", resp.data)
        self.assertGreaterEqual(len(resp.data["trades"]), 1)
