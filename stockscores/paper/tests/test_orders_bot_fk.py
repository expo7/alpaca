from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from paper.models import PaperPortfolio, PaperOrder
from ranker.models import Bot, BotConfig, StrategySpec


class PaperOrderBotFilterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="botorder", password="pass1234")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="P1",
            base_currency="USD",
            starting_balance=Decimal("100000"),
            cash_balance=Decimal("100000"),
            equity=Decimal("100000"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            status="active",
        )
        spec = StrategySpec.objects.create(user=self.user, name="s", spec={"entry_tree": {"type": "condition"}, "parameters": {}})
        cfg = BotConfig.objects.create(user=self.user, name="cfg", config={"symbols": ["AAPL"]})
        self.bot = Bot.objects.create(user=self.user, name="B", strategy_spec=spec, bot_config=cfg)

    def test_bot_field_persists_and_filters(self):
        o1 = PaperOrder.objects.create(
            portfolio=self.portfolio,
            bot=self.bot,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=Decimal("1"),
            status="new",
        )
        o2 = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="buy",
            order_type="market",
            quantity=Decimal("1"),
            status="new",
        )
        self.assertEqual(o1.bot_id, self.bot.id)
        self.assertIsNone(o2.bot_id)

        client = APIClient()
        client.force_authenticate(user=self.user)
        with self.settings(ROOT_URLCONF="stockscores.urls"):
            resp_all = client.get("/api/paper/orders/")
            self.assertEqual(resp_all.status_code, 200)
            data_all = resp_all.json()
            self.assertEqual(len(data_all), 2)

            resp_filtered = client.get(f"/api/paper/orders/?bot={self.bot.id}")
            self.assertEqual(resp_filtered.status_code, 200)
            data_filtered = resp_filtered.json()
            self.assertEqual(len(data_filtered), 1)
            self.assertEqual(data_filtered[0]["id"], o1.id)
