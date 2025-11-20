from decimal import Decimal
from datetime import datetime, timedelta

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase

from paper.models import PaperPortfolio, PaperOrder
from paper.services.execution import ExecutionEngine
from paper.services.market_data import Quote


User = get_user_model()


class DummyProvider:
    def __init__(self, price_map):
        self.price_map = price_map

    def get_quote(self, symbol: str) -> Quote:
        return self.price_map[symbol]

    def get_history_period(self, symbol: str, period="3mo", interval="1d"):
        dates = pd.date_range(end=datetime.utcnow(), periods=50, freq="D")
        data = {
            "Open": [self.price_map[symbol].price] * len(dates),
            "High": [self.price_map[symbol].price] * len(dates),
            "Low": [self.price_map[symbol].price] * len(dates),
            "Close": [self.price_map[symbol].price] * len(dates),
            "Volume": [1_000_000] * len(dates),
        }
        return pd.DataFrame(data, index=dates)


class ExecutionEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="exec-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Exec",
            base_currency="USD",
            status="active",
        )

    def test_iceberg_partial_fills(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="limit",
            tif="day",
            quantity=Decimal("100"),
            reserve_quantity=Decimal("20"),
            limit_price=Decimal("150"),
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {
                "AAPL": Quote("AAPL", price=140, timestamp=datetime.utcnow()),
            }
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        order.refresh_from_db()
        self.assertEqual(order.status, "part_filled")
        self.assertEqual(order.filled_quantity, Decimal("20"))
        prev_qty = order.filled_quantity
        iteration = 0
        while order.status != "filled" and iteration < 10:
            engine.run()
            order.refresh_from_db()
            iteration += 1
            self.assertGreater(order.filled_quantity, prev_qty)
            prev_qty = order.filled_quantity
        self.assertEqual(order.filled_quantity, Decimal("100"))
        self.assertEqual(order.status, "filled")

    def test_cross_symbol_condition(self):
        order.refresh_from_db()
        self.assertEqual(order.status, "filled")
        self.assertEqual(order.filled_quantity, Decimal("100"))

    def test_cross_symbol_condition(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="TSLA",
            side="buy",
            order_type="market",
            tif="day",
            quantity=Decimal("10"),
            condition_type="cross_symbol",
            condition_payload={"symbol": "QQQ", "operator": "gt"},
             extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {
                "TSLA": Quote("TSLA", price=200, timestamp=datetime.utcnow()),
                "QQQ": Quote("QQQ", price=350, timestamp=datetime.utcnow()),
            }
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        order.refresh_from_db()
        self.assertEqual(order.status, "filled")
