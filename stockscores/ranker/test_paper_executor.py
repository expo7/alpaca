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
            "entry_deadline": date(2026, 9, 11),
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
        client = Mock()
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
        client = Mock()
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
