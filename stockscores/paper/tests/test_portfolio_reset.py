from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from paper.api.views import PortfolioViewSet
from paper.models import PaperPortfolio, PaperPosition, PortfolioResetLog


User = get_user_model()


class PortfolioResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="reset-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Demo",
            base_currency="USD",
            starting_balance=Decimal("100000"),
            cash_balance=Decimal("90000"),
            equity=Decimal("95000"),
            realized_pnl=Decimal("5000"),
            unrealized_pnl=Decimal("-1000"),
            status="active",
        )
        PaperPosition.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            quantity=Decimal("10"),
            avg_price=Decimal("100"),
            market_value=Decimal("1000"),
            unrealized_pnl=Decimal("0"),
        )
        self.factory = APIRequestFactory()

    def test_reset_portfolio_wipes_positions_and_logs(self):
        view = PortfolioViewSet.as_view({"post": "reset"})
        request = self.factory.post(f"/paper/portfolios/{self.portfolio.id}/reset/", {"reason": "test"})
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.portfolio.id)
        self.assertEqual(response.status_code, 200)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash_balance, self.portfolio.starting_balance)
        self.assertEqual(self.portfolio.equity, self.portfolio.starting_balance)
        self.assertEqual(self.portfolio.positions.count(), 0)
        log = PortfolioResetLog.objects.filter(portfolio=self.portfolio).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.performed_by, self.user)
