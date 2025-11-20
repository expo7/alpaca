from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from paper.api.views import OrderViewSet, PortfolioViewSet
from paper.models import PaperPortfolio, PaperPosition


User = get_user_model()


class RiskLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="risk-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Risky",
            base_currency="USD",
            starting_balance=Decimal("100000"),
            cash_balance=Decimal("100000"),
            equity=Decimal("100000"),
            status="active",
            max_single_position_pct=Decimal("50"),  # $50k cap per name
            max_gross_exposure_pct=Decimal("100"),  # $100k gross cap
        )
        PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            quantity=Decimal("100"),
            avg_price=Decimal("100"),
            market_value=Decimal("10000"),
            unrealized_pnl=Decimal("0"),
        )
        self.factory = APIRequestFactory()

    def test_single_position_cap_blocks_order(self):
        view = OrderViewSet.as_view({"post": "create"})
        data = {
            "portfolio": self.portfolio.id,
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "tif": "day",
            "quantity": "1000",
            "limit_price": "100",  # notional 100k; exceeds 50k cap when added to 10k existing
        }
        request = self.factory.post("/paper/orders/", data)
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 403)

    def test_gross_exposure_cap_blocks_new_symbol(self):
        view = OrderViewSet.as_view({"post": "create"})
        data = {
            "portfolio": self.portfolio.id,
            "symbol": "MSFT",
            "side": "buy",
            "order_type": "limit",
            "tif": "day",
            "quantity": "950",
            "limit_price": "100",  # notional 95k + existing 10k -> 105k > 100k cap
        }
        request = self.factory.post("/paper/orders/", data)
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 403)

    def test_deposit_and_withdraw(self):
        view = PortfolioViewSet.as_view({"post": "deposit"})
        request = self.factory.post(f"/paper/portfolios/{self.portfolio.id}/deposit/", {"amount": "5000"})
        force_authenticate(request, user=self.user)
        resp = view(request, pk=self.portfolio.id)
        self.assertEqual(resp.status_code, 200)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash_balance, Decimal("105000"))
        withdraw_view = PortfolioViewSet.as_view({"post": "withdraw"})
        request_w = self.factory.post(f"/paper/portfolios/{self.portfolio.id}/withdraw/", {"amount": "3000"})
        force_authenticate(request_w, user=self.user)
        resp_w = withdraw_view(request_w, pk=self.portfolio.id)
        self.assertEqual(resp_w.status_code, 200)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash_balance, Decimal("102000"))
