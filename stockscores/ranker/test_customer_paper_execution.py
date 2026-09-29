import json
import os
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from .alpaca_paper import load_paper_config
from .customer_paper_broker import CustomerBrokerError, CustomerPaperClient, encrypt_credentials, reserve_request, verify_customer_account
from .customer_paper_execution import create_execution, process_execution, run_customer_paper
from .models import CustomerPaperConnection, CustomerPaperExecution, TradeSignal, TradeSignalUpdate


class CustomerPaperTests(APITestCase):
    def setUp(self):
        cache.clear()
        cache.set("customer-paper-worker-heartbeat", True, 45)
        self.env = patch.dict(os.environ, {
            "CUSTOMER_PAPER_CREDENTIAL_KEY": Fernet.generate_key().decode(),
            "CUSTOMER_PAPER_CONNECT_ENABLED": "true", "CUSTOMER_PAPER_EXECUTION_ENABLED": "true",
            "CUSTOMER_PAPER_CUSTOMERS_ENABLED": "false", "ALPACA_PAPER_API_KEY": "", "SHADOW_ALPACA_PAPER_API_KEY": "",
            "ALPACA_PAPER_SECRET_KEY": "", "SHADOW_ALPACA_PAPER_SECRET_KEY": "",
        })
        self.env.start(); self.addCleanup(self.env.stop)
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin-paper", is_superuser=True, is_staff=True)
        self.customer = User.objects.create_user(username="reader-paper")
        self.staff = User.objects.create_user(username="staff-paper", is_staff=True)
        self.client.force_authenticate(self.admin)
        self.connection = CustomerPaperConnection.objects.create(user=self.admin, alpaca_account_id="customer-1234",
            auth_method="api_key", encrypted_access_token=encrypt_credentials("paper-key-12345", "paper-secret-123456"), trading_authorized=True)
        self.broker = Mock()
        self.broker.config = load_paper_config()
        self.broker.base_url = "https://paper-api.alpaca.markets"
        self.broker.account.return_value = {"id": "customer-1234", "status": "ACTIVE", "options_trading_level": 2, "options_buying_power": "25000", "cash": "25000"}
        self.broker.clock.return_value = {"is_open": True}
        self.broker.positions.return_value = []
        self.broker._request.return_value = []
        self.broker.submit_limit_order.return_value = {"id": "customer-entry", "status": "accepted"}
        self.broker.submit_stop_order.return_value = {"id": "customer-stop", "status": "accepted"}
        self.quote = patch("ranker.customer_paper_execution.shared_option_quote", return_value={"ask": Decimal("7"), "bid": Decimal("6.8"), "spread_pct": Decimal("3")})
        self.quote.start(); self.addCleanup(self.quote.stop)

    def signal(self, **overrides):
        values = dict(symbol="QQQ", instrument_type="call", strike=Decimal("500"),
            expiration=timezone.localdate()+timedelta(days=20), status="open", entry_low=Decimal("6"),
            entry_high=Decimal("8"), initial_stop=Decimal("4"), target_1=Decimal("12"), thesis="Fixture",
            paper_execution_enabled=True, paper_entry_order_id="house-entry", paper_submitted_at=timezone.now())
        values.update(overrides)
        return TradeSignal.objects.create(**values)

    def row(self, **overrides):
        values = dict(connection=self.connection, signal=self.signal(), symbol="QQQ-contract", entry_limit=Decimal("7"),
            stop=Decimal("4"), target=Decimal("12"), source="manual")
        values.update(overrides)
        return CustomerPaperExecution.objects.create(**values)

    def test_admin_only_backend_and_switch_opens_own_account(self):
        for user in (self.customer, self.staff):
            self.client.force_authenticate(user)
            for path in ("connection/", "account/", "executions/"):
                self.assertEqual(self.client.get("/api/alpaca-paper/"+path).status_code, 403)
            self.assertEqual(self.client.post("/api/alpaca-paper/connection/", {}).status_code, 403)
        with patch.dict(os.environ, {"CUSTOMER_PAPER_CUSTOMERS_ENABLED": "true"}):
            self.client.force_authenticate(self.customer)
            data = self.client.get("/api/alpaca-paper/connection/").data
            self.assertFalse(data["connected"])
            self.assertEqual(self.client.get("/api/alpaca-paper/executions/").data["executions"], [])

    def test_credentials_are_encrypted_not_returned_and_failed_verification_preserves_old_pair(self):
        old = self.connection.encrypted_access_token
        with patch("ranker.customer_paper_views.CustomerPaperClient", return_value=self.broker):
            result = self.client.post("/api/alpaca-paper/connection/", {"api_key": "new-paper-key-123", "api_secret": "new-paper-secret-123"})
            self.assertEqual(result.status_code, 201)
            self.assertNotIn("new-paper", json.dumps(result.data, default=str))
            self.connection.refresh_from_db()
            self.assertNotEqual(old, self.connection.encrypted_access_token)
            self.assertNotIn("new-paper", self.connection.encrypted_access_token)
            transport = CustomerPaperClient(self.connection)
            self.assertEqual(transport.headers["APCA-API-KEY-ID"], "new-paper-key-123")
            before = self.connection.encrypted_access_token
            self.broker.account.side_effect = CustomerBrokerError("HTTP 401", code=401)
            self.assertEqual(self.client.post("/api/alpaca-paper/connection/", {"api_key": "bad-paper-key-123", "api_secret": "bad-paper-secret-123"}).status_code, 400)
            self.connection.refresh_from_db()
            self.assertEqual(before, self.connection.encrypted_access_token)

    def test_internal_accounts_are_rejected(self):
        with patch("ranker.customer_paper_broker.reserved_account_ids", return_value=["customer-1234"]):
            with self.assertRaises(CustomerBrokerError):
                verify_customer_account(self.broker)

    def test_transport_exact_paper_redacted_errors_no_redirect_or_automatic_retry(self):
        client = CustomerPaperClient(self.connection)
        with patch("ranker.customer_paper_broker.requests.request") as request:
            with self.assertRaises(CustomerBrokerError):
                client._request("GET", "https://api.alpaca.markets/v2/account")
            request.assert_not_called()
            request.return_value = Mock(status_code=401, text="secret material")
            with self.assertRaisesRegex(CustomerBrokerError, "HTTP 401") as error:
                client.account()
            self.assertNotIn("secret", str(error.exception))
            self.assertFalse(request.call_args.kwargs["allow_redirects"])
            self.assertEqual(request.call_count, 1)

    def test_budgets_are_per_account_with_global_backoff(self):
        with patch("ranker.customer_paper_broker.time.time", return_value=120):
            for _ in range(12):
                reserve_request("first")
            with self.assertRaises(CustomerBrokerError):
                reserve_request("first")
            reserve_request("second")
        client = CustomerPaperClient(self.connection)
        with patch("ranker.customer_paper_broker.requests.request", return_value=Mock(status_code=429, headers={"Retry-After": "90"})):
            with self.assertRaises(CustomerBrokerError):
                client.account()
        with self.assertRaises(CustomerBrokerError):
            reserve_request("different-customer")

    def test_consent_limits_pause_and_disconnect_guard(self):
        path = "/api/alpaca-paper/connection/"
        self.assertEqual(self.client.patch(path, {"mirror_enabled": True}, format="json").status_code, 400)
        result = self.client.patch(path, {"mirror_enabled": True, "consent": True, "max_trade_notional": "2500", "max_open_positions": 3}, format="json")
        self.assertEqual(result.status_code, 200)
        self.connection.refresh_from_db()
        self.assertIsNotNone(self.connection.consent_at)
        self.row(state="open", filled_quantity=1)
        self.assertEqual(self.client.delete(path).status_code, 409)
        self.assertEqual(self.client.patch(path, {"mirror_enabled": False}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(path, {"max_trade_notional": "NaN"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(path, {"max_open_positions": True}, format="json").status_code, 400)

    def test_manual_order_and_house_record_remain_independent(self):
        signal = self.signal()
        before = TradeSignal.objects.filter(pk=signal.pk).values().get()
        update_count = TradeSignalUpdate.objects.count()
        with patch("ranker.customer_paper_views.CustomerPaperClient", return_value=self.broker), patch("ranker.customer_paper_execution.CustomerPaperClient", return_value=self.broker):
            path = "/api/alpaca-paper/executions/"
            self.assertEqual(self.client.post(path, {"signal_id": signal.pk, "action": "preview"}, format="json").status_code, 200)
            self.assertEqual(self.broker.submit_limit_order.call_count, 0)
            self.assertEqual(self.client.post(path, {"signal_id": signal.pk, "action": "submit", "confirm_paper": True}, format="json").status_code, 201)
            self.assertEqual(self.client.post(path, {"signal_id": signal.pk, "action": "submit", "confirm_paper": True}, format="json").status_code, 409)
        row = CustomerPaperExecution.objects.get()
        self.assertEqual(row.quantity, 1)
        self.assertEqual(row.entry_order_id, "customer-entry")
        self.assertEqual(TradeSignal.objects.filter(pk=signal.pk).values().get(), before)
        self.assertEqual(TradeSignalUpdate.objects.count(), update_count)

    def test_budget_options_access_and_existing_inventory_block_entries(self):
        signal = self.signal()
        self.connection.max_trade_notional = 500
        with self.assertRaisesRegex(CustomerBrokerError, "budget"):
            create_execution(self.connection, signal, client=self.broker)
        self.connection.max_trade_notional = 1000
        self.broker.account.return_value["options_trading_level"] = 1
        with self.assertRaisesRegex(CustomerBrokerError, "level 2"):
            create_execution(self.connection, signal, client=self.broker)
        self.broker.account.return_value["options_trading_level"] = 2
        self.broker.positions.return_value = [{"symbol": signal.contract_symbol, "qty": "1"}]
        with self.assertRaisesRegex(CustomerBrokerError, "already has"):
            create_execution(self.connection, signal, client=self.broker)
        self.broker.submit_limit_order.assert_not_called()
        self.assertEqual(CustomerPaperExecution.objects.count(), 0)

    def test_timeout_durable_intent_is_reconciled_never_replayed(self):
        signal = self.signal()
        self.broker.submit_limit_order.side_effect = CustomerBrokerError("Unconfirmed response")
        with self.assertRaises(CustomerBrokerError):
            create_execution(self.connection, signal, client=self.broker)
        row = CustomerPaperExecution.objects.get()
        self.assertTrue(row.entry_attempted)
        self.broker.find_order.return_value = None
        self.assertEqual(process_execution(row, self.broker), "unconfirmed")
        self.assertEqual(self.broker.submit_limit_order.call_count, 1)
        self.broker.find_order.return_value = {"id": "recovered", "status": "accepted"}
        self.assertEqual(process_execution(row, self.broker), "entry_pending")
        self.assertEqual(row.entry_order_id, "recovered")

    def test_fills_get_protection_and_exits_continue_with_entry_switch_off(self):
        row = self.row(state="entry_pending", entry_order_id="customer-entry")
        self.broker.order.return_value = {"id": "customer-entry", "status": "filled", "filled_qty": "1", "filled_avg_price": "7"}
        self.broker.positions.return_value = [{"symbol": row.symbol, "qty": "1"}]
        with patch.dict(os.environ, {"CUSTOMER_PAPER_EXECUTION_ENABLED": "false"}):
            self.assertEqual(process_execution(row, self.broker, entries_paused=True), "exit_pending")
        self.assertEqual(row.exit_order_id, "customer-stop")
        self.broker.submit_stop_order.assert_called_once()
        self.broker.order.return_value = {"status": "filled", "filled_qty": "1", "filled_avg_price": "4"}
        self.assertEqual(process_execution(row, self.broker, entries_paused=True), "closed")
        self.assertEqual(row.exit_fill, Decimal("4"))

    def test_manual_order_is_not_canceled_when_mirroring_is_off(self):
        row = self.row(state="entry_pending", entry_order_id="manual-entry")
        self.broker.order.return_value = {"status": "accepted", "filled_qty": "0"}
        with patch("ranker.customer_paper_execution.CustomerPaperClient", return_value=self.broker):
            self.assertEqual(run_customer_paper(self.connection.pk)["status"], "checked")
        self.broker.cancel_order.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, "entry_pending")

    def test_stop_target_switch_confirms_cancel_and_cannot_double_sell(self):
        row = self.row(state="exit_pending", exit_order_id="old-stop", exit_kind="stop", filled_quantity=1, entry_fill=7)
        self.broker.order.return_value = {"status": "new", "filled_qty": "0", "stop_price": "4"}
        self.broker.positions.return_value = [{"symbol": row.symbol, "qty": "1"}]
        with patch("ranker.customer_paper_execution.shared_option_quote", return_value={"bid": Decimal("11"), "ask": Decimal("11.1"), "spread_pct": 1}):
            self.assertEqual(process_execution(row, self.broker), "exit_cancel_pending")
            self.assertEqual(process_execution(row, self.broker), "exit_cancel_pending")
        self.broker.submit_limit_order.assert_not_called()
        # Original stop filled while cancellation was in flight: no second sell.
        self.broker.order.return_value = {"status": "filled", "filled_qty": "1", "filled_avg_price": "4"}
        self.assertEqual(process_execution(row, self.broker), "closed")
        self.broker.submit_limit_order.assert_not_called()

    def test_only_fresh_house_entries_after_consent_are_mirrored(self):
        self.connection.mirror_enabled = True
        self.connection.consent_at = timezone.now()-timedelta(seconds=30)
        self.connection.save()
        old = self.signal(symbol="SPY", paper_submitted_at=timezone.now()-timedelta(minutes=10))
        fresh = self.signal()
        with patch("ranker.customer_paper_execution.CustomerPaperClient", return_value=self.broker):
            run_customer_paper(self.connection.pk)
            self.assertEqual(list(self.connection.executions.values_list("signal_id", flat=True)), [fresh.pk])
            self.broker.order.return_value = {"status": "accepted", "filled_qty": "0"}
            run_customer_paper(self.connection.pk)
        self.assertEqual(self.broker.submit_limit_order.call_count, 1)
        self.assertFalse(self.connection.executions.filter(signal=old).exists())

    def test_missing_position_requires_confirmation_and_stop_tightening_replaces_old_order(self):
        row = self.row(state="open", filled_quantity=1, entry_fill=7)
        self.assertEqual(process_execution(row, self.broker), "confirming_position_inventory")
        row.refresh_from_db()
        self.assertEqual(row.state, "open")
        self.broker.positions.return_value = [{"symbol": row.symbol, "qty": "1"}]
        self.assertEqual(process_execution(row, self.broker), "exit_pending")
        row.signal.current_stop = Decimal("5")
        row.signal.save(update_fields=["current_stop"])
        self.broker.order.return_value = {"status": "new", "filled_qty": "0", "stop_price": "4"}
        self.assertEqual(process_execution(row, self.broker), "exit_cancel_pending")
        self.broker.cancel_order.assert_called_once_with("customer-stop")

    def test_stale_customer_worker_blocks_new_orders(self):
        cache.delete("customer-paper-worker-heartbeat")
        with self.assertRaisesRegex(CustomerBrokerError, "worker"):
            create_execution(self.connection, self.signal(), client=self.broker)
        self.broker.submit_limit_order.assert_not_called()

    def test_duplicate_response_with_delayed_lookup_remains_reconcilable(self):
        self.broker.submit_limit_order.side_effect = CustomerBrokerError("HTTP 422", code=422)
        self.broker.find_order.return_value = None
        with self.assertRaises(CustomerBrokerError):
            create_execution(self.connection, self.signal(), client=self.broker)
        row = CustomerPaperExecution.objects.get()
        self.assertEqual(row.state, "entry_intent")
        self.assertTrue(row.entry_attempted)
        self.broker.find_order.return_value = {"id": "late-original", "status": "filled"}
        self.assertEqual(process_execution(row, self.broker), "entry_pending")
        self.assertEqual(row.entry_order_id, "late-original")
        self.assertEqual(self.broker.submit_limit_order.call_count, 1)
