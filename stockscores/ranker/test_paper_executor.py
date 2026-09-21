from datetime import date, timedelta
from decimal import Decimal
import os
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from .models import TradeSignal, TradeSignalUpdate
from .tasks import run_paper_trade_executor


EXECUTOR_SETTINGS = {
    "ALPACA_PAPER_EXECUTION_ENABLED": "true",
    "ALPACA_PAPER_MAX_OPEN_POSITIONS": "2",
    "ALPACA_PAPER_MAX_SPREAD_PCT": "8",
    "ALPACA_PAPER_CONFIRM_SECONDS": "60",
}


class PaperExecutorTests(TestCase):
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
        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "order"])
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
    def test_open_signal_uses_monitored_exits_without_submitting_oco(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
            paper_last_error="Broker OCO unsupported: legacy rejection",
        )
        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "order"])
        client.clock.return_value = {"is_open": True}
        client.option_quote.return_value = {
            "bid": Decimal("6.90"),
            "ask": Decimal("7.00"),
            "midpoint": Decimal("6.95"),
            "spread_pct": Decimal("1.44"),
        }
        client_class.return_value = client

        result = run_paper_trade_executor()

        signal.refresh_from_db()
        self.assertEqual(result["signals"][str(signal.pk)], "position_open")
        self.assertEqual(signal.paper_exit_order_id, "")
        self.assertEqual(signal.paper_exit_reason, "")
        self.assertEqual(signal.paper_last_error, "")
        client.option_quote.assert_called_once_with("NVDA261016C00240000")
        self.assertFalse(hasattr(client, "submit_oco_exit"))

    @patch.dict(os.environ, EXECUTOR_SETTINGS)
    @patch("ranker.tasks.AlpacaPaperClient")
    def test_monitored_target_submits_single_closing_order(self, client_class):
        signal = self.signal(
            status=TradeSignal.STATUS_OPEN,
            actual_entry=Decimal("6.88"),
            paper_entry_order_id="paper-entry-1",
        )
        client = Mock(spec=["clock", "option_quote", "submit_limit_order", "order"])
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
        self.assertEqual(result["signals"][str(signal.pk)], "exit_submitted")
        self.assertEqual(signal.paper_exit_order_id, "paper-exit-1")
        self.assertEqual(signal.paper_exit_reason, "target_1")
        client.submit_limit_order.assert_called_once_with(
            symbol="NVDA261016C00240000",
            quantity=1,
            side="sell",
            limit_price=Decimal("13.10"),
            client_order_id=f"quantelle-{signal.pk}-exit",
        )

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
