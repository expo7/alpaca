from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase


User = get_user_model()


class DefaultPortfolioOnboardingTests(TestCase):
    def test_creates_default_portfolio_on_user_creation(self):
        user = User.objects.create_user(username="auto-user", password="pass123")
        portfolios = user.paper_portfolios.all()

        self.assertEqual(portfolios.count(), 1)
        portfolio = portfolios.first()
        self.assertEqual(portfolio.name, "Default")
        self.assertEqual(portfolio.status, "active")
        self.assertEqual(portfolio.base_currency, "USD")
        self.assertEqual(portfolio.cash_balance, Decimal("100000"))
        self.assertEqual(portfolio.equity, Decimal("100000"))
        self.assertEqual(portfolio.starting_balance, Decimal("100000"))

    def test_does_not_duplicate_on_subsequent_saves(self):
        user = User.objects.create_user(username="auto-user-2", password="pass123")
        self.assertEqual(user.paper_portfolios.count(), 1)

        user.email = "test@example.com"
        user.save()

        self.assertEqual(user.paper_portfolios.count(), 1)
