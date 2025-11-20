from decimal import Decimal
from datetime import datetime

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from paper.engine.runner import StrategyRunner
from paper.models import PaperPortfolio, Strategy, PaperOrder, StrategyRunLog
from paper.services.execution import ExecutionEngine, ConditionEvaluator
from paper.services.market_data import Quote


User = get_user_model()


class DummyMarketData:
    def __init__(self, price=100):
        self.price = price

    def get_quote(self, symbol):
        return Quote(
            symbol=symbol,
            price=self.price,
            timestamp=datetime.utcnow(),
            volume=1_000_000,
        )

    def get_history_period(self, symbol: str, period="3mo", interval="1d"):
        idx = pd.date_range(datetime.utcnow(), periods=5)
        data = {
            "Open": [self.price] * 5,
            "High": [self.price] * 5,
            "Low": [self.price] * 5,
            "Close": [self.price] * 5,
            "Volume": [1_000_000] * 5,
        }
        return pd.DataFrame(data, index=idx)


class StrategyRunnerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="runner-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Paper One",
            base_currency="USD",
            status="active",
        )
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="Template Strat",
            is_active=True,
            config={
                "symbols": ["AAPL"],
                "order_templates": {
                    "long_entry": {
                        "side": "buy",
                        "order_type": "limit",
                        "limit_price": "100",
                        "tif": "day",
                    },
                    "long_exit": {
                        "side": "sell",
                        "order_type": "stop",
                        "stop_price": "90",
                        "tif": "gtc",
                    },
                },
                "entry": {
                    "template": "long_entry",
                    "order": {
                        "limit_price": "105",
                        "quantity_pct": 10,
                    },
                    "rules": {
                        "type": "rule",
                        "condition": "price",
                        "payload": {"operator": "gte", "value": 0},
                    },
                },
                "exit": {
                    "template": "long_exit",
                    "order": {
                        "stop_price": "95",
                    },
                    "rules": {
                        "type": "rule",
                        "condition": "price",
                        "payload": {"operator": "gte", "value": 0},
                    },
                },
            },
        )
        self.market = DummyMarketData(price=150)
        self.runner = StrategyRunner()
        self.runner.market_data = self.market
        self.runner.execution_engine = ExecutionEngine(data_provider=self.market)
        self.runner.condition_evaluator = ConditionEvaluator(self.market)

    def test_templates_merge_with_overrides(self):
        now = timezone.now()
        self.runner.evaluate(self.strategy, self.portfolio, now)
        orders = list(
            PaperOrder.objects.filter(strategy=self.strategy).order_by("id")
        )
        self.assertEqual(len(orders), 2)
        entry, exit_order = orders
        self.assertEqual(entry.order_type, "limit")
        self.assertEqual(entry.side, "buy")
        # quantity_pct 10% of starting equity (100000)
        self.assertEqual(entry.quantity.quantize(Decimal("1.000000")), Decimal("10000"))
        self.assertEqual(entry.limit_price, Decimal("105"))
        self.assertEqual(entry.tif, "day")
        self.assertEqual(exit_order.order_type, "stop")
        self.assertEqual(exit_order.side, "sell")
        self.assertEqual(exit_order.stop_price, Decimal("95"))
        self.assertEqual(exit_order.tif, "gtc")
        log = StrategyRunLog.objects.get(strategy=self.strategy, portfolio=self.portfolio)
        self.assertEqual(len(log.generated_orders), 2)

    def test_exit_only_trigger_when_entry_fails(self):
        config = self.strategy.config
        config["entry"]["rules"]["payload"]["value"] = 1_000_000  # impossible price
        config["exit"]["order"]["trail_amount"] = "5"
        self.strategy.config = config
        self.strategy.save(update_fields=["config"])
        now = timezone.now()
        self.runner.evaluate(self.strategy, self.portfolio, now)
        orders = PaperOrder.objects.filter(strategy=self.strategy)
        self.assertEqual(orders.count(), 1)
        exit_order = orders.first()
        self.assertEqual(exit_order.order_type, "stop")
        self.assertEqual(exit_order.stop_price, Decimal("95"))
        self.assertEqual(exit_order.trail_amount, Decimal("5"))
        log = StrategyRunLog.objects.get(strategy=self.strategy, portfolio=self.portfolio)
        self.assertEqual(len(log.generated_orders), 1)

    def test_should_run_frequency_gating(self):
        strategy = Strategy.objects.create(
            user=self.user,
            name="Freq Strat",
            is_active=True,
            last_run_at=timezone.now(),
            config={"frequency": "1h"},
        )
        now = timezone.now()
        self.assertFalse(self.runner._should_run(strategy, now))
        later = now + timezone.timedelta(seconds=4000)
        self.assertTrue(self.runner._should_run(strategy, later))

    def test_multi_symbol_orders(self):
        config = self.strategy.config
        config["symbols"] = ["AAPL", "MSFT"]
        self.strategy.config = config
        self.strategy.save(update_fields=["config"])
        now = timezone.now()
        self.runner.evaluate(self.strategy, self.portfolio, now)
        orders = PaperOrder.objects.filter(strategy=self.strategy).order_by("symbol", "side")
        self.assertEqual(orders.count(), 4)
        symbols = {order.symbol for order in orders}
        self.assertEqual(symbols, {"AAPL", "MSFT"})
        log = StrategyRunLog.objects.filter(strategy=self.strategy).latest("run_at")
        self.assertEqual(len(log.generated_orders), 4)
