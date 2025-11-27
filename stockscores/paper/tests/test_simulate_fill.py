from decimal import Decimal
from datetime import timedelta

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from paper.models import PaperOrder, PaperPortfolio
from paper.services.execution import simulate_order_fill

User = get_user_model()


class StubProvider:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def get_history(self, *args, **kwargs):
        return self.df


class SimulateOrderFillTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass1234")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Paper",
            base_currency="USD",
            starting_balance=Decimal("100000"),
            cash_balance=Decimal("100000"),
            equity=Decimal("100000"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            status="active",
        )

    def _bars(self, start_price: float = 10.0, high: float | None = None, low: float | None = None):
        now = timezone.now()
        idx = pd.date_range(end=now, periods=3, freq="1min", tz="UTC")
        data = {
          "Open": [start_price, start_price, start_price],
          "High": [high or start_price, high or start_price, high or start_price],
          "Low": [low or start_price, low or start_price, low or start_price],
          "Close": [start_price, start_price, start_price],
          "Volume": [1000, 1000, 1000],
        }
        return pd.DataFrame(data, index=idx)

    def test_market_order_fills_on_first_bar(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=Decimal("10"),
            status="new",
        )
        provider = StubProvider(self._bars(start_price=12.5))
        updated = simulate_order_fill(order, data_provider=provider)
        updated.refresh_from_db()
        self.portfolio.refresh_from_db()
        self.assertEqual(updated.status, "filled")
        self.assertEqual(updated.filled_quantity, Decimal("10"))
        self.assertEqual(updated.average_fill_price, Decimal("12.5"))
        self.assertLess(self.portfolio.cash_balance, Decimal("100000"))

    def test_limit_buy_respects_price(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="buy",
            order_type="limit",
            quantity=Decimal("5"),
            limit_price=Decimal("9"),
            status="new",
        )
        provider = StubProvider(self._bars(start_price=12.0, low=8.5, high=12.5))
        updated = simulate_order_fill(order, data_provider=provider)
        updated.refresh_from_db()
        self.assertEqual(updated.status, "filled")
        self.assertEqual(updated.average_fill_price, Decimal("9"))

        # Reset and use a price that should not fill
        order2 = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="buy",
            order_type="limit",
            quantity=Decimal("5"),
            limit_price=Decimal("5"),
            status="new",
        )
        provider2 = StubProvider(self._bars(start_price=12.0, low=11.5, high=12.5))
        updated2 = simulate_order_fill(order2, data_provider=provider2)
        updated2.refresh_from_db()
        self.assertEqual(updated2.status, "working")

    def test_api_simulate_fill_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=Decimal("1"),
            status="new",
        )
        with self.settings(ROOT_URLCONF="stockscores.urls"):
            with self.subTest("basic call"):
                # Patch provider via simple DataFrame
                provider = StubProvider(self._bars(start_price=5.0))
                # Monkeypatch simulate_order_fill to use provider
                from paper.api import views as paper_views
                orig = paper_views.simulate_order_fill
                try:
                    paper_views.simulate_order_fill = lambda ord: orig(ord, data_provider=provider)
                    resp = client.post(f"/api/paper/orders/{order.id}/simulate_fill/")
                finally:
                    paper_views.simulate_order_fill = orig
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "filled")

    def test_day_order_expires_if_not_filled_next_day(self):
        # No fill in bars and check next day -> canceled for DAY
        submitted = timezone.now() - timedelta(days=1, hours=1)
        idx = pd.date_range(end=submitted + timedelta(hours=1), periods=2, freq="1min", tz="UTC")
        data = {"Open": [500, 500], "High": [500, 500], "Low": [500, 500], "Close": [500, 500], "Volume": [100, 100]}
        provider = StubProvider(pd.DataFrame(data, index=idx))
        order = PaperOrder.objects.create(
          portfolio=self.portfolio,
          symbol="MSFT",
          side="buy",
          order_type="limit",
          quantity=Decimal("1"),
          limit_price=Decimal("200"),
          status="new",
          tif="day",
        )
        order.created_at = submitted
        order.save(update_fields=["created_at"])
        updated = simulate_order_fill(order, check_time=submitted + timedelta(days=1, hours=2), data_provider=provider)
        updated.refresh_from_db()
        self.assertEqual(updated.status, "canceled")

    def test_gtc_order_remains_pending_across_days(self):
        submitted = timezone.now() - timedelta(days=1, hours=1)
        idx = pd.date_range(end=submitted + timedelta(hours=1), periods=2, freq="1min", tz="UTC")
        data = {"Open": [500, 500], "High": [500, 500], "Low": [500, 500], "Close": [500, 500], "Volume": [100, 100]}
        provider = StubProvider(pd.DataFrame(data, index=idx))
        order = PaperOrder.objects.create(
          portfolio=self.portfolio,
          symbol="MSFT",
          side="buy",
          order_type="limit",
          quantity=Decimal("1"),
          limit_price=Decimal("200"),
          status="new",
          tif="gtc",
        )
        order.created_at = submitted
        order.save(update_fields=["created_at"])
        updated = simulate_order_fill(order, check_time=submitted + timedelta(days=1, hours=2), data_provider=provider)
        updated.refresh_from_db()
        self.assertNotEqual(updated.status, "canceled")
