from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from paper.models import PaperPortfolio, PaperPosition, Instrument


User = get_user_model()


class PerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="perf-user", password="pass1234")
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
        self.instrument = Instrument.objects.create(symbol="AAPL")

    def test_performance_unrealized_uses_positions(self):
        PaperPosition.objects.create(
            instrument=self.instrument,
            portfolio=self.portfolio,
            symbol="AAPL",
            quantity=Decimal("10"),
            avg_price=Decimal("100"),
            market_value=Decimal("1200"),
            unrealized_pnl=Decimal("200"),
        )
        client = APIClient()
        client.force_authenticate(user=self.user)
        with self.settings(ROOT_URLCONF="stockscores.urls"):
            class StubProvider:
                def get_quote(self, symbol):
                    raise Exception("no quote")
            with patch("paper.api.views.get_market_data_provider", return_value=StubProvider()):
                resp = client.get(f"/api/paper/portfolios/{self.portfolio.id}/performance/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["unrealized_pnl"], "200.00")

    def test_performance_uses_live_quotes_for_market_value(self):
        PaperPosition.objects.create(
            instrument=self.instrument,
            portfolio=self.portfolio,
            symbol="AAPL",
            quantity=Decimal("10"),
            avg_price=Decimal("100"),
            market_value=Decimal("1000"),  # stale
            unrealized_pnl=Decimal("0"),
        )

        class Quote:
            def __init__(self, price):
                self.price = price

        def fake_provider():
            class Provider:
                def get_quote(self, symbol):
                    return Quote(Decimal("150"))
            return Provider()

        client = APIClient()
        client.force_authenticate(user=self.user)
        with self.settings(ROOT_URLCONF="stockscores.urls"):
            with patch("paper.api.views.get_market_data_provider", side_effect=fake_provider):
                resp = client.get(f"/api/paper/portfolios/{self.portfolio.id}/performance/")
        self.assertEqual(resp.status_code, 200)
        # Equity should reflect live market value 10 * 150 + cash 100000 = 101500
        self.assertEqual(resp.data["equity"], "101500.00")
        # Unrealized should reflect 10 * (150-100) = 500
        self.assertEqual(resp.data["unrealized_pnl"], "500.00")
