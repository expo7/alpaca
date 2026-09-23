from datetime import date, timedelta
from decimal import Decimal
import os
from unittest.mock import ANY, Mock, patch

from django.test import TestCase
from django.utils import timezone

from .models import TradeExecutorHealth, TradeSignal, TradeSignalUpdate
from .tasks import run_execution_guardian, run_paper_trade_executor


EXECUTOR_SETTINGS = {
    "ALPACA_PAPER_EXECUTION_ENABLED": "true",
    "ALPACA_PAPER_MAX_OPEN_POSITIONS": "2",
    "ALPACA_PAPER_MAX_SPREAD_PCT": "8",
    "ALPACA_PAPER_CONFIRM_SECONDS": "60",
}


class PaperExecutorTests(TestCase):
    def setUp(self):
        TradeExecutorHealth.objects.create(
            status=TradeExecutorHealth.STATUS_HEALTHY,
            entries_paused=False,
            last_completed_at=timezone.now(),
            last_success_at=timezone.now(),
        )

    def signal(self, **overrides):
        values = {
            "symbol": "NVDA",
            "instrument_type": "call",
            "strike": Decimal("240"),
            "expiration": date(2026, 10, 16),
            "status": TradeSignal.STATUS_PUBLISHED,
            "risk_level": "high",
            "trigger_direction": "above",
            "underlying_trigger_price": Decimal("234.80"),
            "do_not_chase_price": Decimal("9.00"),
            "entry_deadline": timezone.localdate() + timedelta(days=3),
            "entry_low": Decimal("6.50"),
            "entry_high": Decimal("9.00"),
            "initial_stop": Decimal("4.25"),
            "current_stop": Decimal("4.25"),
            "target_1": Decimal("13.00"),
            "thesis": "Relative strength breakout.",
            "paper_execution_enabled": True,
            "paper_quantity": 1,
            "trigger_first_seen_at": timezone.now() - timedelta(minutes=2),
        }
        values.update(overrides)
        return TradeSignal.objects.create(**values)

    @patch.dict(os.environ, {"ALPACA_PAPER_EXECUTION_ENABLED": "false"})
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_global_switch_prevents_client_creation(self, client_class):
        result = run_paper_trade_executor()
        self.assertEqual(result["status"], "disabled")
        client_class.assert_not_called()

        health = TradeExecutorHealth.objects.get(singleton_id=1)
        self.assertEqual(health.status, TradeExecutorHealth.STATUS_DISABLED)
        self.assertTrue(health.entries_paused)

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_degraded_guardian_blocks_new_entries_but_keeps_open_exit_path(self, client_class):
        pending = self.signal()
        open_signal = self.signal(
            symbol="AMD",
            strike=Decimal("200"),
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-open",
            initial_stop=Decimal("4.25"),
            current_stop=Decimal("4.25"),
        )
        health = TradeExecutorHealth.objects.get(singleton_id=1)
        health.status = TradeExecutorHealth.STATUS_DEGRADED
        health.entries_paused = True
        health.consecutive_failures = 1
        health.last_error = "stale heartbeat"
        health.save()

        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "submit_market_order", "order"])
        client.clock.return_value = {"is_open": True}
        client.option_quote.return_value = {
            "bid": Decimal("4.10"),
            "ask": Decimal("4.30"),
            "midpoint": Decimal("4.20"),
            "spread_pct": Decimal("4.76"),
        }
        client.submit_market_order.return_value = {"id": "paper-stop-exit-guardian", "status": "accepted"}
        client_class.return_value = client

        result = run_paper_trade_executor()

        pending.refresh_from_db()
        open_signal.refresh_from_db()
        self.assertEqual(result["signals"][str(pending.pk)], "entry_guardian_paused")
        self.assertEqual(pending.paper_entry_order_id, "")
        self.assertEqual(result["signals"][str(open_signal.pk)], "monitored_stop_fallback_submitted")
        self.assertEqual(open_signal.paper_exit_order_id, "paper-stop-exit-guardian")
        client.submit_market_order.assert_called_once()

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_guardian_marks_stale_executor_degraded(self, client_class):
        health = TradeExecutorHealth.objects.get(singleton_id=1)
        health.last_started_at = timezone.now() - timedelta(minutes=2)
        health.last_completed_at = timezone.now() - timedelta(minutes=2)
        health.save()
        client = Mock(spec=["clock"])
        client.clock.return_value = {"is_open": True}
        client_class.return_value = client

        result = run_execution_guardian()

        health.refresh_from_db()
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(health.entries_paused)
        self.assertEqual(health.status, TradeExecutorHealth.STATUS_DEGRADED)
        self.assertIn("stale", health.last_error.lower())

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_qualifying_signal_submits_one_paper_limit_order(self, client_class):
        signal = self.signal()
        client = Mock(spec=["clock", "stock_quote", "option_quote", "submit_limit_order", "order"])
        client.clock.return_value = {"is_open": True}
        client.stock_quote.return_value = {"bid": Decimal("235.00"), "ask": Decimal("235.02"), "midpoint": Decimal("235.01")}
        client.option_quote.return_value = {"bid": Decimal("6.80"), "ask": Decimal("6.90"), "midpoint": Decimal("6.85"), "spread_pct": Decimal("1.46")}
        client.submit_limit_order.return_value = {"id": "paper-entry-1", "status": "accepted"}
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "entry_submitted")
        self.assertEqual(signal.paper_entry_order_id, "paper-entry-1")
        client.submit_limit_order.assert_called_once_with(
            symbol="NVDA261016C00240000",
            quantity=1,
            side="buy",
            limit_price=Decimal("6.90"),
            client_order_id=f"quantelle-{signal.pk}-entry",
        )
        self.assertTrue(TradeSignalUpdate.objects.filter(signal=signal, note__contains="Submitted Alpaca paper").exists())

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_filled_entry_becomes_open_and_is_recorded(self, client_class):
        signal = self.signal(paper_entry_order_id="paper-entry-1", paper_order_status="accepted")
        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "submit_market_order", "order"])
        client.clock.return_value = {"is_open": True}
        client.order.return_value = {
            "status": "filled",
            "filled_avg_price": "6.88",
            "filled_at": timezone.now().isoformat(),
        }
        client_class.return_value = client

        run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(signal.status, TradeSignal.STATUS_OPEN)
        self.assertEqual(signal.actual_entry, Decimal("6.88"))
        self.assertTrue(TradeSignalUpdate.objects.filter(signal=signal, event_type="triggered").exists())

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_open_signal_places_silent_gtc_broker_stop_by_default(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
            paper_last_error="Broker OCO unsupported: legacy rejection",
        )
        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "submit_market_order", "submit_stop_order", "order"])
        client.clock.return_value = {"is_open": True}
        client.option_quote.return_value = {
            "bid": Decimal("6.90"),
            "ask": Decimal("7.00"),
            "midpoint": Decimal("6.95"),
            "spread_pct": Decimal("1.44"),
        }
        client.submit_stop_order.return_value = {"id": "paper-stop-1", "status": "accepted"}
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "broker_exit_protection_submitted")
        self.assertEqual(signal.paper_exit_order_id, "paper-stop-1")
        self.assertEqual(signal.paper_exit_reason, "broker_stop")
        self.assertEqual(signal.paper_last_error, "")
        client.option_quote.assert_called_once_with("NVDA261016C00240000")
        client.submit_stop_order.assert_called_once_with(
            symbol="NVDA261016C00240000",
            quantity=1,
            stop_price=Decimal("4.25"),
            client_order_id=ANY,
        )
        self.assertFalse(TradeSignalUpdate.objects.filter(signal=signal, event_type="exit_submitted").exists())

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_position_near_target_places_silent_gtc_take_profit(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
        )
        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "submit_market_order", "order"])
        client.clock.return_value = {"is_open": True}
        client.option_quote.return_value = {
            "bid": Decimal("13.10"),
            "ask": Decimal("13.20"),
            "midpoint": Decimal("13.15"),
            "spread_pct": Decimal("0.76"),
        }
        client.submit_limit_order.return_value = {"id": "paper-exit-1", "status": "accepted"}
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "broker_exit_protection_submitted")
        self.assertEqual(signal.paper_exit_order_id, "paper-exit-1")
        self.assertEqual(signal.paper_exit_reason, "broker_target")
        client.submit_limit_order.assert_called_once_with(
            symbol="NVDA261016C00240000",
            quantity=1,
            side="sell",
            limit_price=Decimal("13.00"),
            client_order_id=ANY,
            time_in_force="gtc",
        )
        self.assertFalse(TradeSignalUpdate.objects.filter(signal=signal, event_type="exit_submitted").exists())

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_monitored_stop_submits_market_close_to_avoid_stranded_limit(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
        )
        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "submit_market_order", "order"])
        client.clock.return_value = {"is_open": True}
        client.option_quote.return_value = {
            "bid": Decimal("4.10"),
            "ask": Decimal("4.30"),
            "midpoint": Decimal("4.20"),
            "spread_pct": Decimal("4.76"),
        }
        client.submit_market_order.return_value = {"id": "paper-stop-exit-1", "status": "accepted"}
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "monitored_stop_fallback_submitted")
        self.assertEqual(signal.paper_exit_order_id, "paper-stop-exit-1")
        self.assertEqual(signal.paper_exit_reason, "stop")
        client.submit_market_order.assert_called_once_with(
            symbol="NVDA261016C00240000",
            quantity=1,
            side="sell",
            client_order_id=ANY,
        )
        client.submit_limit_order.assert_not_called()
        self.assertFalse(TradeSignalUpdate.objects.filter(signal=signal, event_type="exit_submitted").exists())

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_broker_stop_switches_to_target_without_overlapping_orders(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
            paper_exit_order_id="paper-stop-1",
            paper_exit_reason="broker_stop",
        )
        client = Mock(spec=["clock", "option_quote", "order", "cancel_order", "submit_limit_order"])
        client.clock.return_value = {"is_open": True}
        client.order.return_value = {"status": "accepted"}
        client.option_quote.return_value = {
            "bid": Decimal("11.50"), "ask": Decimal("11.60"),
            "midpoint": Decimal("11.55"), "spread_pct": Decimal("0.87"),
        }
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "broker_exit_switch_pending")
        self.assertEqual(signal.paper_exit_order_id, "paper-stop-1")
        self.assertEqual(signal.paper_order_status, "pending_cancel")
        client.cancel_order.assert_called_once_with("paper-stop-1")
        client.submit_limit_order.assert_not_called()

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_confirmed_cancel_is_replaced_with_one_target_order(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
            paper_exit_order_id="paper-stop-1",
            paper_exit_reason="broker_stop",
        )
        client = Mock(spec=["clock", "option_quote", "order", "submit_limit_order"])
        client.clock.return_value = {"is_open": True}
        client.order.return_value = {"status": "canceled"}
        client.option_quote.return_value = {
            "bid": Decimal("11.50"), "ask": Decimal("11.60"),
            "midpoint": Decimal("11.55"), "spread_pct": Decimal("0.87"),
        }
        client.submit_limit_order.return_value = {"id": "paper-target-1", "status": "accepted"}
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "broker_exit_protection_submitted")
        self.assertEqual(signal.paper_exit_order_id, "paper-target-1")
        self.assertEqual(signal.paper_exit_reason, "broker_target")
        self.assertFalse(TradeSignalUpdate.objects.filter(signal=signal, event_type="execution_warning").exists())

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_target_order_switches_back_to_stop_only_below_hysteresis(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
            paper_exit_order_id="paper-target-1",
            paper_exit_reason="broker_target",
        )
        client = Mock(spec=["clock", "option_quote", "order", "cancel_order"])
        client.clock.return_value = {"is_open": True}
        client.order.return_value = {"status": "accepted"}
        client.option_quote.return_value = {
            "bid": Decimal("8.50"), "ask": Decimal("8.60"),
            "midpoint": Decimal("8.55"), "spread_pct": Decimal("1.17"),
        }
        client_class.return_value = client

        result = run_paper_trade_executor()

        self.assertEqual(result["signals"][str(signal.pk)], "broker_exit_switch_pending")
        client.cancel_order.assert_called_once_with("paper-target-1")

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_pending_cancel_is_not_submitted_or_cancelled_again(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
            paper_exit_order_id="paper-stop-1",
            paper_exit_reason="broker_stop",
            paper_order_status="pending_cancel",
        )
        client = Mock(spec=["clock", "option_quote", "order", "cancel_order", "submit_limit_order"])
        client.clock.return_value = {"is_open": True}
        client.order.return_value = {"status": "pending_cancel"}
        client.option_quote.return_value = {
            "bid": Decimal("11.50"), "ask": Decimal("11.60"),
            "midpoint": Decimal("11.55"), "spread_pct": Decimal("0.87"),
        }
        client_class.return_value = client

        result = run_paper_trade_executor()

        self.assertEqual(result["signals"][str(signal.pk)], "broker_exit_switch_pending")
        client.cancel_order.assert_not_called()
        client.submit_limit_order.assert_not_called()

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_filled_oco_leg_closes_signal_and_records_reason(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
            paper_exit_order_id="paper-oco-1",
            paper_exit_reason="oco",
        )
        client = Mock()
        client.clock.return_value = {"is_open": True}
        client.order.return_value = {
            "status": "canceled",
            "legs": [{
                "status": "filled",
                "filled_avg_price": "13.00",
                "filled_at": timezone.now().isoformat(),
                "limit_price": "13.00",
                "stop_price": None,
            }],
        }
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "exit_filled")
        self.assertEqual(signal.status, TradeSignal.STATUS_CLOSED)
        self.assertEqual(signal.final_exit, Decimal("13.00"))
        self.assertEqual(signal.paper_exit_reason, "target_1")
        client.order.assert_called_once_with("paper-oco-1", nested=True)
