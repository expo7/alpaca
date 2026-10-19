from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from .models import ResearchRun, ShadowSetup, ShadowExecutorHealth, TradeExecutorHealth
from .shadow_executor import _entry, _open, _submit_entry, run_shadow_cycle
from .shadow_broker import ShadowPaperClient, ShadowIdentityError


class ShadowExecutorTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        run = ResearchRun.objects.create(expected_run_at=self.now, started_at=self.now,
                                         completed_at=self.now, session_type="regular")
        self.setup = ShadowSetup.objects.create(
            research_run=run, request_id="shadow-executor-test", decided_at=self.now,
            contract_symbol="SPY261023C00500000",
            category="index", execution_mode="broker_intended", ruleset_version="shadow-v1",
            decision={"symbol": "SPY", "direction": "bullish", "option_symbol": "SPY261023C00500000",
                      "expiration": "2026-10-23", "entry_low": "5.00", "entry_high": "5.50", "do_not_chase": "5.50",
                      "entry_deadline": (self.now + timedelta(hours=1)).isoformat(), "underlying_invalidation": "490",
                      "underlying_trigger_price": "500", "trigger_direction": "above", "confirmation_seconds": 60,
                      "stop": "4.00", "target_1": "8.00", "contract_multiplier": 100},
        )
        self.client = Mock()
        self.client.positions.return_value = []
        self.client.stock_quote.return_value = {"midpoint": Decimal("501")}
        self.client.option_quote.return_value = {"bid": Decimal("5.00"), "ask": Decimal("5.20"), "spread_pct": Decimal("3.92")}
        self.client.submit_limit_order.return_value = {"id": "shadow-entry-order", "status": "accepted"}
        entry_approval = patch.dict("os.environ", {"SHADOW_ALLOWED_SETUP_ID": str(self.setup.pk),
                                               "SHADOW_AUTONOMOUS_ENTRIES_ENABLED": "false"})
        entry_approval.start()
        self.addCleanup(entry_approval.stop)

    def test_disabled_cycle_does_not_construct_client_or_identify_account(self):
        factory, identify = Mock(), Mock()
        with patch.dict("os.environ", {"SHADOW_TRADING_ENABLED": "false"}):
            self.assertEqual(run_shadow_cycle(client_factory=factory, identity=identify)["status"], "disabled")
        factory.assert_not_called()
        identify.assert_not_called()

    def test_confirmation_limit_and_durable_entry_intent(self):
        self.assertEqual(_entry(self.setup, self.client, "shadow-id", self.now, 2, 1), "confirming_trigger")
        self.assertEqual(_entry(self.setup, self.client, "shadow-id", self.now + timedelta(seconds=61), 2, 1), "entry_submitted")
        self.client.submit_limit_order.assert_called_once()
        self.assertEqual(self.setup.broker_account_id, "shadow-id")
        self.assertEqual(self.setup.events.filter(kind="entry_intent").count(), 1)
        self.client.order.return_value = {"id": "shadow-entry-order", "status": "accepted"}
        self.assertEqual(_entry(self.setup, self.client, "shadow-id", self.now + timedelta(seconds=62), 2, 1), "entry_pending")
        self.client.submit_limit_order.assert_called_once()

    def test_explicit_first_setup_approval_required(self):
        with patch.dict("os.environ", {"SHADOW_ALLOWED_SETUP_ID": "", "SHADOW_AUTONOMOUS_ENTRIES_ENABLED": "false"}):
            self.assertEqual(_entry(self.setup, self.client, "shadow-id", self.now, 2, 1), "entry_not_approved")
        self.client.submit_limit_order.assert_not_called()

    def test_ambiguous_submission_never_retries(self):
        self.client.submit_limit_order.side_effect = RuntimeError("network timeout")
        with self.assertRaises(RuntimeError):
            _submit_entry(self.setup, self.client, "shadow-id", self.now, Decimal("5.20"))
        self.setup.refresh_from_db()
        self.assertEqual(self.setup.broker_entry_client_id, f"quantelle-shadow-{self.setup.pk}-entry")
        self.assertEqual(self.setup.events.filter(kind="entry_intent").count(), 1)
        self.client.by_client_id.side_effect = RuntimeError("not found")
        with self.assertRaises(RuntimeError):
            _entry(self.setup, self.client, "shadow-id", self.now + timedelta(seconds=1), 2, 1)
        self.client.submit_limit_order.assert_called_once()

    def test_filled_entry_submits_one_stop_and_reconciles_fill(self):
        self.setup.broker_entry_client_id = f"quantelle-shadow-{self.setup.pk}-entry"
        self.setup.broker_entry_order_id = "entry-id"
        self.setup.broker_account_id = "shadow-id"
        self.setup.save()
        self.client.order.return_value = {"id": "entry-id", "status": "filled", "filled_avg_price": "5.20",
                                          "filled_at": self.now.isoformat()}
        self.client.positions.return_value = [{"symbol": self.setup.decision["option_symbol"], "qty": "1"}]
        self.client.submit_stop_order.return_value = {"id": "stop-id", "status": "accepted"}
        self.assertEqual(_entry(self.setup, self.client, "shadow-id", self.now + timedelta(seconds=1), 2, 1), "exit_submitted")
        self.assertEqual(self.setup.status, "active")
        self.client.submit_stop_order.assert_called_once()
        self.assertEqual(self.setup.broker_protection_kind, "stop")
        self.client.order.return_value = {"id": "stop-id", "status": "filled", "filled_avg_price": "3.90",
                                          "filled_at": (self.now + timedelta(minutes=3)).isoformat()}
        self.client.positions.return_value = []
        self.assertEqual(_open(self.setup, self.client, self.now + timedelta(minutes=3)), "completed")
        self.assertEqual(Decimal(self.setup.result["realized_return_dollars"]), Decimal("-130.00"))
        self.assertNotIn("unrealized_return_pct", self.setup.result)

    def test_target_switch_waits_for_cancel_confirmation(self):
        self.setup.status = "active"
        self.setup.result = {"broker_entry": "5.00", "mfe_pct": "0", "mae_pct": "0", "result_type": "broker"}
        self.setup.broker_exit_client_id = f"quantelle-shadow-{self.setup.pk}-stop-1"
        self.setup.broker_exit_order_id = "stop-id"
        self.setup.broker_protection_kind = "stop"
        self.setup.entered_at = self.now
        self.setup.save()
        self.client.positions.return_value = [{"symbol": self.setup.decision["option_symbol"], "qty": "1"}]
        self.client.order.return_value = {"id": "stop-id", "status": "accepted"}
        self.client.option_quote.return_value = {"bid": Decimal("7.10"), "ask": Decimal("7.20")}
        self.assertEqual(_open(self.setup, self.client, self.now), "cancel_pending")
        self.client.submit_limit_order.assert_not_called()
        self.assertEqual(_open(self.setup, self.client, self.now + timedelta(seconds=1)), "cancel_pending")
        self.client.cancel_order.assert_called_once()
        self.client.order.return_value = {"id": "stop-id", "status": "canceled"}
        self.client.submit_limit_order.return_value = {"id": "target-id", "status": "accepted"}
        self.assertEqual(_open(self.setup, self.client, self.now + timedelta(seconds=2)), "exit_submitted")
        self.assertEqual(self.setup.broker_protection_kind, "target")

    def test_client_never_falls_back_to_primary(self):
        with patch.dict("os.environ", {"SHADOW_TRADING_ENABLED": "true", "SHADOW_EXECUTION_CONFIRMED": "true",
                                    "SHADOW_EMERGENCY_PAUSE": "false", "SHADOW_ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                                    "SHADOW_ALPACA_PAPER_API_KEY": "", "ALPACA_PAPER_API_KEY": "primary",
                                    "ALPACA_PAPER_SECRET_KEY": "primary-secret"}):
            with self.assertRaises(ShadowIdentityError):
                ShadowPaperClient()

    def test_expiry_and_limits_never_submit_entry(self):
        self.assertEqual(_entry(self.setup, self.client, "shadow-id", self.now + timedelta(hours=2), 2, 1), "expired_unfilled")
        self.client.submit_limit_order.assert_not_called()
        self.setup.status = "proposed"
        self.setup.save(update_fields=["status"])
        from .models import ShadowEvent
        ShadowEvent.objects.create(setup=self.setup, kind="entry_intent", occurred_at=self.now)
        self.assertEqual(_entry(self.setup, self.client, "shadow-id", self.now, 1, 1), "daily_limit")
        self.client.submit_limit_order.assert_not_called()

    def test_stale_quote_rejected_by_shadow_client(self):
        with patch.dict("os.environ", {"SHADOW_TRADING_ENABLED": "true", "SHADOW_EXECUTION_CONFIRMED": "true",
                                    "SHADOW_EMERGENCY_PAUSE": "false", "SHADOW_ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                                    "SHADOW_ALPACA_PAPER_API_KEY": "shadow", "SHADOW_ALPACA_PAPER_SECRET_KEY": "secret"}):
            client = ShadowPaperClient()
            from .alpaca_paper import PaperTradingError
            with self.assertRaises(PaperTradingError):
                client._require_fresh_quote((timezone.now() - timedelta(minutes=1)).isoformat())

    def test_shadow_order_transport_uses_only_shadow_headers(self):
        with patch.dict("os.environ", {"SHADOW_TRADING_ENABLED": "true", "SHADOW_EXECUTION_CONFIRMED": "true",
                                    "SHADOW_EMERGENCY_PAUSE": "false", "SHADOW_ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                                    "SHADOW_ALPACA_PAPER_API_KEY": "shadow-key", "SHADOW_ALPACA_PAPER_SECRET_KEY": "shadow-secret",
                                    "ALPACA_PAPER_API_KEY": "primary-key", "ALPACA_PAPER_SECRET_KEY": "primary-secret"}):
            client = ShadowPaperClient()
            response = Mock(status_code=200, content=b"{}", json=Mock(return_value={"id": "paper-1"}))
            with patch("ranker.alpaca_paper.requests.request", return_value=response) as request:
                client.submit_limit_order(symbol="SPY261023C00500000", quantity=1, side="buy",
                                          limit_price=Decimal("5.20"), client_order_id="quantelle-shadow-1-entry")
            self.assertEqual(request.call_args.kwargs["headers"]["APCA-API-KEY-ID"], "shadow-key")
            self.assertEqual(request.call_args.kwargs["headers"]["APCA-API-SECRET-KEY"], "shadow-secret")
            self.assertTrue(request.call_args.args[1].startswith("https://paper-api.alpaca.markets/"))

    def test_full_cycle_isolated_from_primary_guardian(self):
        self.client.clock.return_value = {"is_open": True}
        identity = Mock(return_value="shadow-id")
        flags = {"SHADOW_TRADING_ENABLED": "true", "SHADOW_EXECUTION_CONFIRMED": "true",
                 "SHADOW_EMERGENCY_PAUSE": "false", "SHADOW_ALLOWED_SETUP_ID": str(self.setup.pk)}
        with patch.dict("os.environ", flags), patch("ranker.shadow_executor.connection") as db:
            db.vendor = "postgresql"
            db.cursor.return_value.__enter__.return_value.fetchone.return_value = (True,)
            first = run_shadow_cycle(client_factory=lambda: self.client, identity=identity, now=self.now)
            self.assertEqual(first["setups"][str(self.setup.pk)], "confirming_trigger")
            second = run_shadow_cycle(client_factory=lambda: self.client, identity=identity,
                                      now=self.now + timedelta(seconds=61))
            self.assertEqual(second["setups"][str(self.setup.pk)], "entry_submitted")
            self.client.order.return_value = {"id": "shadow-entry-order", "status": "filled",
                                              "filled_avg_price": "5.20", "filled_at": (self.now + timedelta(seconds=62)).isoformat()}
            self.client.positions.return_value = [{"symbol": self.setup.contract_symbol, "qty": "1"}]
            self.client.submit_stop_order.return_value = {"id": "stop-id", "status": "accepted"}
            third = run_shadow_cycle(client_factory=lambda: self.client, identity=identity,
                                     now=self.now + timedelta(seconds=62))
            self.assertEqual(third["setups"][str(self.setup.pk)], "exit_submitted")
        self.assertEqual(ShadowExecutorHealth.objects.get(singleton_id=1).verified_account_id, "shadow-id")
        self.assertFalse(TradeExecutorHealth.objects.exists())
