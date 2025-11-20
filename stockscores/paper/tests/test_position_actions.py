from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from paper.api.views import PositionViewSet
from paper.models import PaperPortfolio, PaperPosition
from paper.services.market_data import Quote


User = get_user_model()


class FakeProvider:
    def __init__(self, price):
        self.price = price

    def get_quote(self, symbol):
        return Quote(symbol=symbol, price=self.price, timestamp=None)


class PositionActionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="pos-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Pos",
            base_currency="USD",
            starting_balance=Decimal("100000"),
            cash_balance=Decimal("100000"),
            equity=Decimal("100000"),
            status="active",
        )
        self.position = PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            quantity=Decimal("10"),
            avg_price=Decimal("100"),
            market_value=Decimal("1000"),
            unrealized_pnl=Decimal("0"),
        )
        self.factory = APIRequestFactory()

    @patch("paper.api.views.get_market_data_provider")
    def test_close_position(self, mock_provider):
        mock_provider.return_value = FakeProvider(price=Decimal("200"))
        view = PositionViewSet.as_view({"post": "close"})
        req = self.factory.post(f"/api/paper/positions/{self.position.id}/close/")
        force_authenticate(req, user=self.user)
        resp = view(req, pk=self.position.id)
        self.assertEqual(resp.status_code, 200)
        self.position.refresh_from_db()
        self.portfolio.refresh_from_db()
        self.assertEqual(self.position.quantity, Decimal("0"))
        self.assertEqual(self.position.market_value, Decimal("0"))
        self.assertGreater(self.portfolio.cash_balance, Decimal("100000"))
        self.assertGreater(self.portfolio.realized_pnl, Decimal("0"))

    @patch("paper.api.views.get_market_data_provider")
    def test_rebalance_position(self, mock_provider):
        mock_provider.return_value = FakeProvider(price=Decimal("200"))
        view = PositionViewSet.as_view({"post": "rebalance"})
        req = self.factory.post(
            f"/api/paper/positions/{self.position.id}/rebalance/",
            {"target_pct": "20"},
        )
        force_authenticate(req, user=self.user)
        resp = view(req, pk=self.position.id)
        self.assertEqual(resp.status_code, 200)
        self.position.refresh_from_db()
        self.assertGreater(self.position.quantity, Decimal("10"))
        self.assertGreater(self.position.market_value, Decimal("0"))
