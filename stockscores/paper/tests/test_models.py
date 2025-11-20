from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from paper.models import PaperPortfolio, PaperPosition
from paper.api.serializers import PaperOrderSerializer

User = get_user_model()


class PaperModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="tester")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Test Portfolio",
            base_currency="USD",
            status="active",
        )

    def test_position_unique_per_symbol(self):
        PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            quantity=Decimal("10"),
            avg_price=Decimal("100"),
            market_value=Decimal("1000"),
            unrealized_pnl=Decimal("0"),
        )
        duplicate = PaperPosition(
            portfolio=self.portfolio,
            symbol="AAPL",
            quantity=Decimal("5"),
            avg_price=Decimal("90"),
            market_value=Decimal("450"),
            unrealized_pnl=Decimal("0"),
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class PaperOrderSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="serializer-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Serializer Portfolio",
            base_currency="USD",
            status="active",
        )

    def test_requires_quantity_or_notional(self):
        payload = {
            "portfolio": self.portfolio.id,
            "symbol": "MSFT",
            "side": "buy",
            "order_type": "limit",
            "tif": "day",
            "limit_price": "300",
        }
        serializer = PaperOrderSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Specify either quantity or notional.",
            serializer.errors["non_field_errors"][0],
        )

    def test_limit_requires_price(self):
        payload = {
            "portfolio": self.portfolio.id,
            "symbol": "AMZN",
            "side": "buy",
            "order_type": "limit",
            "tif": "day",
            "quantity": "5",
        }
        serializer = PaperOrderSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "limit_price is required for this order type.",
            serializer.errors["non_field_errors"][0],
        )

    def test_trailing_needs_trail_value(self):
        payload = {
            "portfolio": self.portfolio.id,
            "symbol": "TSLA",
            "side": "sell",
            "order_type": "trailing_amount",
            "tif": "day",
            "quantity": "2",
        }
        serializer = PaperOrderSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Provide trail_amount or trail_percent for trailing orders.",
            serializer.errors["non_field_errors"][0],
        )

    def test_conditional_requires_payload(self):
        payload = {
            "portfolio": self.portfolio.id,
            "symbol": "NFLX",
            "side": "buy",
            "order_type": "market",
            "tif": "day",
            "quantity": "1",
            "condition_type": "price",
        }
        serializer = PaperOrderSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "condition_payload is required for conditional orders.",
            serializer.errors["non_field_errors"][0],
        )

    def test_slippage_fee_overrides_roundtrip(self):
        payload = {
            "portfolio": self.portfolio.id,
            "symbol": "SHOP",
            "side": "buy",
            "order_type": "market",
            "tif": "day",
            "quantity": "10",
            "slippage_mode": "fixed",
            "slippage_fixed": "0.12",
            "fee_mode": "bps",
            "fee_bps": "5",
        }
        serializer = PaperOrderSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.notes.get("slippage_mode"), "fixed")
        self.assertEqual(order.notes.get("slippage_fixed"), "0.1200")
        self.assertEqual(order.notes.get("fee_mode"), "bps")
        self.assertEqual(order.notes.get("fee_bps"), "5.0000")
        data = PaperOrderSerializer(order).data
        self.assertEqual(data["slippage_mode"], "fixed")
        self.assertEqual(data["slippage_fixed"], "0.1200")
        self.assertEqual(data["fee_mode"], "bps")
        self.assertEqual(data["fee_bps"], "5.0000")
