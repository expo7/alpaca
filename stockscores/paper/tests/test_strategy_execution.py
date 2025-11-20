from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from paper.models import PaperPortfolio, Strategy


User = get_user_model()


class StrategyExecutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="exec-user")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user, name="P1", base_currency="USD", status="active"
        )
        self.strategy = Strategy.objects.create(
            user=self.user, name="Strat", description="", config={}
        )

    def test_execute_returns_queued(self):
        url = f"/api/paper/strategies/{self.strategy.id}/execute/"
        res = self.client.post(
            url,
            {"strategy_id": self.strategy.id, "portfolio_id": self.portfolio.id},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["status"], "queued")
        self.assertEqual(res.data["strategy_id"], self.strategy.id)
        self.assertIn(self.portfolio.id, res.data["portfolios"])
        self.assertIn("execution_id", res.data)

    def test_execute_rejects_missing_portfolio(self):
        url = f"/api/paper/strategies/{self.strategy.id}/execute/"
        res = self.client.post(
            url,
            {"strategy_id": self.strategy.id},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_execute_rejects_foreign_portfolio(self):
        other_user = User.objects.create(username="other")
        other_port = PaperPortfolio.objects.create(
            user=other_user, name="P2", base_currency="USD", status="active"
        )
        url = f"/api/paper/strategies/{self.strategy.id}/execute/"
        res = self.client.post(
            url,
            {"strategy_id": self.strategy.id, "portfolio_id": other_port.id},
            format="json",
        )
        self.assertEqual(res.status_code, 404)
