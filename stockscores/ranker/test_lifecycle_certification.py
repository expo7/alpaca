from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .alpaca_paper import PaperTradingError
from .lifecycle_audit import audit_lifecycles, audit_trade_signal
from .models import (
    OperationalTelegramAlert,
    TelegramNotification,
    TradeExecutorHealth,
    TradeLifecycleCertification,
    TradeSignal,
    TradeSignalUpdate,
)


class LifecycleCertificationTests(TestCase):
    def make_signal(self, status=TradeSignal.STATUS_CLOSED, **overrides):
        now = timezone.now()
        values = {
            "symbol": "MU", "instrument_type": "call", "strike": Decimal("150"),
            "expiration": now.date() + timedelta(days=30), "status": status,
            "entry_low": Decimal("4"), "initial_stop": Decimal("3"), "target_1": Decimal("6"),
            "actual_entry": Decimal("4.25") if status in {TradeSignal.STATUS_OPEN, TradeSignal.STATUS_CLOSED} else None,
            "final_exit": Decimal("5.50") if status == TradeSignal.STATUS_CLOSED else None,
            "realized_return_pct": Decimal("29.41") if status == TradeSignal.STATUS_CLOSED else None,
            "thesis": "Test", "paper_execution_enabled": True, "paper_quantity": 1,
            "paper_entry_order_id": "entry-1" if status in {TradeSignal.STATUS_OPEN, TradeSignal.STATUS_CLOSED} else "",
            "paper_exit_order_id": "exit-1" if status == TradeSignal.STATUS_CLOSED else "",
            "paper_filled_at": now if status in {TradeSignal.STATUS_OPEN, TradeSignal.STATUS_CLOSED} else None,
            "paper_last_checked_at": now,
        }
        values.update(overrides)
        signal = TradeSignal.objects.create(**values)
        if status in {TradeSignal.STATUS_OPEN, TradeSignal.STATUS_CLOSED}:
            TradeSignalUpdate.objects.create(signal=signal, event_type="triggered", note="Filled")
        if status == TradeSignal.STATUS_CLOSED:
            TradeSignalUpdate.objects.create(signal=signal, event_type="closed", note="Closed")
        for notification in TelegramNotification.objects.filter(update__signal=signal):
            notification.status = TelegramNotification.STATUS_SENT
            notification.sent_at = now
            notification.save(update_fields=["status", "sent_at", "updated_at"])
        return signal

    def broker(self, signal, *, position=True, entry_status="filled", exit_status="filled"):
        orders = []
        if signal.paper_entry_order_id:
            orders.append({"id": signal.paper_entry_order_id, "status": entry_status, "client_order_id": f"quantelle-{signal.pk}-entry"})
        if signal.paper_exit_order_id:
            orders.append({"id": signal.paper_exit_order_id, "status": exit_status, "client_order_id": f"quantelle-{signal.pk}-target-exit"})
        positions = [{"symbol": signal.contract_symbol, "qty": "1"}] if position else []
        return orders, positions

    def set_guardian(self, *, stale=False):
        checked = timezone.now() - (timedelta(minutes=10) if stale else timedelta(seconds=10))
        return TradeExecutorHealth.objects.create(
            singleton_id=1,
            status=TradeExecutorHealth.STATUS_HEALTHY,
            entries_paused=False,
            last_completed_at=checked,
            last_success_at=checked,
        )

    def test_clean_complete_lifecycle_certifies(self):
        signal = self.make_signal()
        self.set_guardian()
        orders, positions = self.broker(signal, position=False)
        report = audit_trade_signal(signal, client=object(), orders=orders, positions=positions)
        self.assertTrue(report.lifecycle_certified)
        self.assertEqual(report.status, TradeLifecycleCertification.STATUS_CERTIFIED)
        self.assertTrue(all(value["result"] in {"pass", "not_applicable"} for value in report.checkpoints.values()))

    def test_pending_and_open_trades_remain_uncertified(self):
        pending = self.make_signal(status=TradeSignal.STATUS_PUBLISHED)
        self.set_guardian()
        pending_report = audit_trade_signal(pending, client=object(), orders=[], positions=[])
        self.assertEqual(pending_report.status, TradeLifecycleCertification.STATUS_PENDING)
        open_signal = self.make_signal(status=TradeSignal.STATUS_OPEN)
        orders, positions = self.broker(open_signal)
        open_report = audit_trade_signal(open_signal, client=object(), orders=orders, positions=positions)
        self.assertEqual(open_report.status, TradeLifecycleCertification.STATUS_PENDING)
        self.assertEqual(open_report.checkpoints["stop_target_monitoring_active"]["result"], "pass")

    def test_broker_database_disagreement_is_persisted_and_alerted_once(self):
        signal = self.make_signal()
        self.set_guardian()
        report = audit_trade_signal(signal, client=object(), orders=[], positions=[])
        self.assertIn("BROKER_ENTRY_MISMATCH", report.discrepancy_codes)
        self.assertEqual(signal.status, TradeSignal.STATUS_CLOSED)
        audit_trade_signal(signal, client=object(), orders=[], positions=[])
        self.assertEqual(OperationalTelegramAlert.objects.filter(signal=signal).count(), 1)

    def test_stale_guardian_heartbeat_fails_open_position(self):
        signal = self.make_signal(status=TradeSignal.STATUS_OPEN)
        self.set_guardian(stale=True)
        orders, positions = self.broker(signal)
        report = audit_trade_signal(signal, client=object(), orders=orders, positions=positions)
        self.assertIn("GUARDIAN_POSITION_UNPROTECTED", report.discrepancy_codes)

    def test_missing_telegram_event_is_detected(self):
        signal = self.make_signal()
        self.set_guardian()
        TelegramNotification.objects.filter(update__signal=signal, update__event_type="closed").update(status=TelegramNotification.STATUS_PENDING)
        orders, positions = self.broker(signal, position=False)
        report = audit_trade_signal(signal, client=object(), orders=orders, positions=positions)
        self.assertIn("TELEGRAM_EVENT_MISSING", report.discrepancy_codes)

    def test_duplicate_lifecycle_event_is_detected(self):
        signal = self.make_signal()
        self.set_guardian()
        TradeSignalUpdate.objects.create(signal=signal, event_type="closed", note="Duplicate")
        orders, positions = self.broker(signal, position=False)
        report = audit_trade_signal(signal, client=object(), orders=orders, positions=positions)
        self.assertIn("DUPLICATE_LIFECYCLE_ARTIFACT", report.discrepancy_codes)

    def test_closure_requires_database_finalization(self):
        signal = self.make_signal(final_exit=None)
        self.set_guardian()
        orders, positions = self.broker(signal, position=False)
        report = audit_trade_signal(signal, client=object(), orders=orders, positions=positions)
        self.assertIn("DATABASE_NOT_FINALIZED", report.discrepancy_codes)

    def test_repeated_clean_runs_update_one_record(self):
        signal = self.make_signal()
        self.set_guardian()
        orders, positions = self.broker(signal, position=False)
        first = audit_trade_signal(signal, client=object(), orders=orders, positions=positions)
        certified_at = first.certified_at
        second = audit_trade_signal(signal, client=object(), orders=orders, positions=positions)
        self.assertEqual(TradeLifecycleCertification.objects.filter(signal=signal).count(), 1)
        self.assertEqual(second.certified_at, certified_at)
        self.assertEqual(second.retry_count, 0)

    def test_alpaca_api_failure_fails_safely(self):
        class BrokenClient:
            def orders(self):
                raise PaperTradingError("unavailable")

        signal = self.make_signal()
        self.set_guardian()
        report = audit_trade_signal(signal, client=BrokenClient(), positions=[])
        self.assertEqual(report.status, TradeLifecycleCertification.STATUS_ERROR)
        self.assertIn("ALPACA_API_FAILURE", report.discrepancy_codes)
        self.assertEqual(signal.status, TradeSignal.STATUS_CLOSED)

    @override_settings(ALPACA_PAPER_EXECUTION_ENABLED=False)
    def test_batch_does_minimal_work_without_candidates(self):
        result = audit_lifecycles()
        self.assertEqual(result, {"status": "idle", "audited": 0})
