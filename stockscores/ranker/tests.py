from datetime import timedelta

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch
import pandas as pd

from .models import StockScore, Bot, BotConfig, StrategySpec
from .scoring import technical_score_from_ta
from .services import compute_and_store
from .serializers import StrategySpecSerializer
from ranker.backtest import BacktestResult, run_basket_backtest
from ranker.tasks import run_bot_once, schedule_due_bots


class TechnicalScoreTests(SimpleTestCase):
    def _build_indicator_frame(self):
        rows = 60
        data = {
            "Close": [100 + i for i in range(rows)],
            "trend_ema_fast": [95 + i for i in range(rows)],
            "trend_ema_slow": [90 + i for i in range(rows)],
            "trend_sma_fast": [94 + i for i in range(rows)],
            "trend_sma_slow": [89 + i for i in range(rows)],
            "trend_adx": [30 for _ in range(rows)],
            "trend_macd_diff": [1.0 for _ in range(rows)],
            "momentum_rsi": [25 for _ in range(rows - 2)] + [20, 60],
            "momentum_roc": [1.0 for _ in range(rows)],
            "momentum_stoch": [80 for _ in range(rows)],
            "volume_obv": [i for i in range(rows)],
            "Volume": [100 for _ in range(rows - 1)] + [200],
            "volatility_atr": [1 + 0.1 * i for i in range(rows)],
            "volatility_bbw": [1 + 0.05 * i for i in range(rows - 1)] + [20],
            "volatility_bbl": [80 for _ in range(rows)],
            "volatility_bbh": [120 for _ in range(rows)],
        }
        return pd.DataFrame(data)

    def test_technical_score_from_ta_returns_weighted_scores(self):
        df = self._build_indicator_frame()

        score, comp = technical_score_from_ta(df)

        self.assertAlmostEqual(score, 23.25)
        self.assertEqual(comp["trend_raw"], 35)
        self.assertEqual(comp["momentum_raw"], 20)
        self.assertEqual(comp["volume_raw"], 20)
        self.assertEqual(comp["volatility_raw"], 10)
        self.assertEqual(comp["meanreversion_raw"], 10)
        self.assertEqual(
            comp["ta_weights"],
            {"trend": 0.35, "momentum": 0.25, "volume": 0.2, "volatility": 0.1, "meanreversion": 0.1},
        )

    def test_technical_score_from_ta_handles_all_nan(self):
        df = pd.DataFrame(
            {
                "Close": [float("nan"), float("nan")],
                "trend_ema_fast": [float("nan"), float("nan")],
            }
        )

        score, comp = technical_score_from_ta(df)

        self.assertEqual(score, 0.0)
        self.assertEqual(comp["error"], "all_nan_after_indicators")


class ComputeAndStoreTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("ranker.services.blended_score")
    def test_compute_and_store_persists_scores_and_uses_cache(self, mock_blended_score):
        mock_blended_score.return_value = (
            55.0,
            60.0,
            50.0,
            {"technical": {"trend_raw": 10}, "fundamental": {"valuation_raw": 5}},
        )

        created = compute_and_store("msft", tech_weight=0.6, fund_weight=0.4)

        self.assertEqual(StockScore.objects.count(), 1)
        self.assertEqual(created.symbol, "MSFT")
        self.assertEqual(created.tech_score, 60.0)
        self.assertEqual(created.fundamental_score, 50.0)
        self.assertEqual(created.final_score, 55.0)
        mock_blended_score.assert_called_once_with("msft", 0.6, 0.4, ta_weights=None)

        cached = compute_and_store("msft", tech_weight=0.6, fund_weight=0.4)
        self.assertEqual(cached.pk, created.pk)
        mock_blended_score.assert_called_once()

    @patch("ranker.services.blended_score")
    def test_compute_and_store_respects_ta_weights_in_extra_and_cache_keys(self, mock_blended_score):
        mock_blended_score.side_effect = [
            (
                55.0,
                60.0,
                50.0,
                {"technical": {"trend_raw": 10}, "fundamental": {"valuation_raw": 5}},
            ),
            (
                45.0,
                50.0,
                40.0,
                {"technical": {"trend_raw": 9}, "fundamental": {"valuation_raw": 4}},
            ),
        ]

        ta_weights_a = {"trend": 0.4, "momentum": 0.6}
        ta_weights_b = {"trend": 0.7, "momentum": 0.3}

        first = compute_and_store(
            "msft",
            tech_weight=0.6,
            fund_weight=0.4,
            extra={"ta_weights": ta_weights_a},
        )

        mock_blended_score.assert_called_once()
        self.assertEqual(mock_blended_score.call_args.kwargs["ta_weights"], ta_weights_a)

        cached = compute_and_store(
            "msft",
            tech_weight=0.6,
            fund_weight=0.4,
            extra={"ta_weights": ta_weights_a},
        )

        self.assertEqual(cached.pk, first.pk)
        self.assertEqual(mock_blended_score.call_count, 1)

        updated = compute_and_store(
            "msft",
            tech_weight=0.6,
            fund_weight=0.4,
            extra={"ta_weights": ta_weights_b},
        )

        self.assertEqual(mock_blended_score.call_count, 2)
        self.assertEqual(mock_blended_score.call_args.kwargs["ta_weights"], ta_weights_b)
        self.assertEqual(StockScore.objects.count(), 1)
        self.assertEqual(updated.pk, first.pk)
        self.assertEqual(updated.final_score, 45.0)


class StrategyApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="apiuser", password="test-pass"
        )
        self.client.force_authenticate(user=self.user)

    def _strategy_payload(self):
        return {
            "name": "RSI Example",
            "entry_tree": {
                "type": "condition",
                "indicator": "rsi",
                "operator": "lt",
                "value": {"param": "rsi_entry"},
            },
            "exit_tree": {
                "type": "condition",
                "indicator": "rsi",
                "operator": "gt",
                "value": {"param": "rsi_exit"},
            },
            "parameters": {
                "rsi_period": {"type": "int", "default": 14},
                "rsi_entry": {"type": "float", "default": 30},
                "rsi_exit": {"type": "float", "default": 70},
            },
        }

    def _bot_payload(self):
        return {
            "symbols": ["AAPL"],
            "mode": "paper",
            "capital": 10_000,
            "rebalance_days": 5,
            "top_n": 1,
        }

    def test_strategy_validate_happy_path(self):
        res = self.client.post(
            "/api/strategies/validate/",
            data=self._strategy_payload(),
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["valid"])

    def test_strategy_validate_missing_param(self):
        payload = self._strategy_payload()
        payload["parameters"]["rsi_exit_typo"] = payload["parameters"].pop("rsi_exit")

        res = self.client.post(
            "/api/strategies/validate/",
            data=payload,
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["valid"])
        errors = res.data["errors"]
        self.assertIsInstance(errors, list)
        self.assertTrue(
            any(
                err.get("field") == "parameters"
                and "rsi_exit" in err.get("message", "")
                for err in errors
            )
        )

    @patch("ranker.views.run_basket_backtest")
    def test_backtest_run_happy_path(self, mock_backtest):
        mock_backtest.return_value = BacktestResult(
            tickers=["AAPL"],
            start="2024-01-01",
            end="2024-01-10",
            equity_curve=[
                {"date": "2024-01-01", "value": 10000.0},
                {"date": "2024-01-10", "value": 10500.0},
            ],
            benchmark_symbol="SPY",
            benchmark_curve=[],
            summary={
                "initial_capital": 10000.0,
                "final_value": 10500.0,
                "total_return": 0.05,
                "max_drawdown": -0.02,
            },
            per_ticker=[],
        )

        res = self.client.post(
            "/api/backtests/run/",
            data={
                "strategy": self._strategy_payload(),
                "bot": self._bot_payload(),
                "start_date": "2024-01-01",
                "end_date": "2024-01-10",
            },
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertIn("trades", res.data)
        self.assertIsInstance(res.data["trades"], list)
        self.assertIn("equity_curve", res.data)
        self.assertIsInstance(res.data["equity_curve"], list)

        stats = res.data.get("stats", {})
        for key in [
            "start_equity",
            "end_equity",
            "return_pct",
            "max_drawdown_pct",
            "num_trades",
            "win_rate_pct",
        ]:
            self.assertIn(key, stats)

    def test_backtest_run_errors_are_structured(self):
        invalid_strategy = self._strategy_payload()
        invalid_strategy["entry_tree"] = {}

        res = self.client.post(
            "/api/backtests/run/",
            data={
                "strategy": invalid_strategy,
                "bot": {"symbols": []},
            },
            format="json",
        )

        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.data["valid"])
        errors = res.data["errors"]
        self.assertIsInstance(errors, list)
        self.assertTrue(
            any(err.get("field") == "strategy.entry_tree" for err in errors)
        )
        self.assertTrue(any(err.get("field") == "bot.symbols" for err in errors))
        self.assertTrue(any(err.get("field") == "dates" for err in errors))


class BacktestEngineAdvancedTests(TestCase):
    def setUp(self):
        self.dates = pd.date_range("2024-01-01", periods=4, freq="D")

    @patch("ranker.backtest.yf.download")
    def test_commission_and_slippage_reduce_equity(self, mock_download):
        basket_df = pd.DataFrame(
            {
                ("Close", "AAA"): [100, 110, 120, 130],
            },
            index=self.dates,
        )
        bench_df = pd.DataFrame({"Close": [100, 101, 102, 103]}, index=self.dates)
        mock_download.side_effect = [basket_df, bench_df, basket_df, bench_df]

        no_cost = run_basket_backtest(
            ["AAA"],
            start="2024-01-01",
            end="2024-01-04",
            rebalance_days=1,
        )

        with_cost = run_basket_backtest(
            ["AAA"],
            start="2024-01-01",
            end="2024-01-04",
            rebalance_days=1,
            commission_per_trade=100.0,
            commission_pct=0.01,
            slippage_model="bps",
            slippage_bps=100,
        )

        self.assertGreater(no_cost.summary["final_value"], with_cost.summary["final_value"])
        self.assertTrue(with_cost.summary["trades"])
        trade = with_cost.summary["trades"][0]
        self.assertIn("commission", trade)
        self.assertIn("slippage_cost", trade)

    @patch("ranker.backtest.yf.download")
    def test_risk_limits_and_stats_present(self, mock_download):
        basket_df = pd.DataFrame(
            {
                ("Close", "AAA"): [100, 102, 104, 106],
                ("Close", "BBB"): [100, 101, 99, 98],
            },
            index=self.dates,
        )
        bench_df = pd.DataFrame({"Close": [100, 101, 102, 103]}, index=self.dates)
        mock_download.side_effect = [basket_df, bench_df]

        result = run_basket_backtest(
            ["AAA", "BBB"],
            start="2024-01-01",
            end="2024-01-04",
            rebalance_days=1,
            max_open_positions=1,
            max_per_position_pct=0.4,
        )

        trade_symbols = {t["symbol"] for t in result.summary.get("trades", [])}
        self.assertLessEqual(len(trade_symbols), 1)

        summary = result.summary
        self.assertIn("volatility_annualized", summary)
        self.assertIn("sharpe_ratio", summary)
        self.assertIn("max_drawdown_duration_bars", summary)

    def test_strategy_spec_allows_event_condition(self):
        data = {
            "entry_tree": {"type": "event_condition", "event": "earnings"},
            "exit_tree": {"type": "condition", "indicator": "rsi", "operator": "gt", "value": {"param": "rsi_exit"}},
            "parameters": {"rsi_exit": {"type": "float", "default": 60}},
        }
        serializer = StrategySpecSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class StrategyTemplateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="template-user", password="test-pass"
        )
        self.client.force_authenticate(user=self.user)

    def test_list_templates(self):
        res = self.client.get("/api/strategies/templates/")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, list)
        ids = {tpl["id"] for tpl in res.data}
        self.assertIn("rsi_dip_buyer", ids)
        self.assertIn("macd_trend_follower", ids)
        for tpl in res.data:
            spec = tpl.get("strategy_spec") or {}
            self.assertTrue(spec.get("entry_tree"))
            self.assertIn("parameters", spec)

    def test_template_detail_and_not_found(self):
        res = self.client.get("/api/strategies/templates/rsi_dip_buyer/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["id"], "rsi_dip_buyer")
        self.assertIn("strategy_spec", res.data)

        missing = self.client.get("/api/strategies/templates/does_not_exist/")
        self.assertEqual(missing.status_code, 404)


class BotRunnerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="botuser", password="test-pass"
        )
        self.client.force_authenticate(user=self.user)
        self.strategy = StrategySpec.objects.create(
            user=self.user,
            name="Momentum",
            spec={
                "entry_tree": {
                    "type": "condition",
                    "indicator": "rsi",
                    "operator": "lt",
                    "value": {"param": "rsi_entry"},
                },
                "exit_tree": {},
                "parameters": {"rsi_entry": {"type": "float", "default": 30}},
                "metadata": {},
            },
        )
        self.bot_config = BotConfig.objects.create(
            user=self.user,
            name="BotCfg",
            config={
                "symbols": ["AAPL"],
                "mode": "paper",
                "capital": 10000,
                "rebalance_days": 5,
                "top_n": 1,
                "benchmark": "SPY",
            },
        )

    @patch("ranker.tasks.run_bot_once.delay")
    def test_start_pause_stop_transitions(self, mock_delay):
        bot = Bot.objects.create(
            user=self.user,
            strategy_spec=self.strategy,
            bot_config=self.bot_config,
            schedule="1m",
        )

        res = self.client.post(
            f"/api/bots/{bot.id}/start/", {"run_now": True}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        bot.refresh_from_db()
        self.assertEqual(bot.state, Bot.STATE_RUNNING)
        self.assertIsNotNone(bot.next_run_at)
        mock_delay.assert_called_once_with(bot.id)

        res = self.client.post(f"/api/bots/{bot.id}/pause/", format="json")
        self.assertEqual(res.status_code, 200)
        bot.refresh_from_db()
        self.assertEqual(bot.state, Bot.STATE_PAUSED)
        self.assertIsNone(bot.next_run_at)

        mock_delay.reset_mock()
        res = self.client.post(f"/api/bots/{bot.id}/start/", format="json")
        self.assertEqual(res.status_code, 200)
        bot.refresh_from_db()
        self.assertEqual(bot.state, Bot.STATE_RUNNING)
        self.assertIsNotNone(bot.next_run_at)
        mock_delay.assert_not_called()

        res = self.client.post(f"/api/bots/{bot.id}/stop/", format="json")
        self.assertEqual(res.status_code, 200)
        bot.refresh_from_db()
        self.assertEqual(bot.state, Bot.STATE_STOPPED)
        self.assertIsNone(bot.next_run_at)

    @patch("ranker.tasks.run_bot_once.delay")
    def test_scheduler_only_enqueues_running_due_bots(self, mock_delay):
        now = timezone.now()
        running_due = Bot.objects.create(
            user=self.user,
            strategy_spec=self.strategy,
            bot_config=self.bot_config,
            state=Bot.STATE_RUNNING,
            next_run_at=now - timedelta(seconds=10),
            schedule="1m",
        )
        Bot.objects.create(
            user=self.user,
            strategy_spec=self.strategy,
            bot_config=self.bot_config,
            state=Bot.STATE_RUNNING,
            next_run_at=now + timedelta(minutes=5),
            schedule="5m",
        )
        Bot.objects.create(
            user=self.user,
            strategy_spec=self.strategy,
            bot_config=self.bot_config,
            state=Bot.STATE_PAUSED,
            next_run_at=now - timedelta(seconds=5),
            schedule="1m",
        )

        schedule_due_bots()

        mock_delay.assert_called_once_with(running_due.id)

    @patch("ranker.tasks.run_bot_engine")
    def test_run_bot_once_respects_state(self, mock_engine):
        bot = Bot.objects.create(
            user=self.user,
            strategy_spec=self.strategy,
            bot_config=self.bot_config,
            state=Bot.STATE_STOPPED,
            schedule="1m",
        )

        run_bot_once(bot.id)
        mock_engine.assert_not_called()

        bot.state = Bot.STATE_RUNNING
        bot.save(update_fields=["state"])

        run_bot_once(bot.id)
        mock_engine.assert_called_once_with(bot)
        bot.refresh_from_db()
        self.assertIsNotNone(bot.last_run_at)
        self.assertIsNotNone(bot.next_run_at)
