from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import TelegramNotification, TradeSignal, TradeSignalUpdate
from .trade_lifecycle import TradeLifecycleError, cancel_pending_signal


class TradeLifecycleTests(TestCase):
    def signal(self, **overrides):
        values = {
            "symbol": "INTC",
            "company_name": "Intel Corporation",
            "instrument_type": "call",
            "strike": Decimal("110"),
            "expiration": "2026-10-16",
            "status": TradeSignal.STATUS_PUBLISHED,
            "risk_level": "high",
            "trigger_direction": "above",
            "underlying_trigger_price": Decimal("110.55"),
            "do_not_chase_price": Decimal("7.90"),
            "entry_low": Decimal("7.20"),
            "entry_high": Decimal("7.90"),
            "initial_stop": Decimal("5.30"),
            "target_1": Decimal("12.00"),
            "thesis": "Breakout setup",
            "paper_execution_enabled": True,
        }
        values.update(overrides)
        return TradeSignal.objects.create(**values)

    def test_cancel_is_atomic_customer_event_with_telegram_outbox(self):
        signal = self.signal()
        result = cancel_pending_signal(
            signal_id=signal.pk,
            note="Cancelled before entry because the premium exceeded the published ceiling.",
        )

        signal.refresh_from_db()
        self.assertEqual(signal.status, TradeSignal.STATUS_CANCELLED)
        self.assertFalse(signal.paper_execution_enabled)
        self.assertIsNotNone(signal.closed_at)
        self.assertEqual(result.update.event_type, "cancelled")
        self.assertEqual(result.update.telegram_notification.status, TelegramNotification.STATUS_PENDING)

    def test_cancel_is_idempotent_and_does_not_duplicate_customer_alert(self):
        signal = self.signal()
        first = cancel_pending_signal(
            signal_id=signal.pk,
            note="Cancelled before entry because the premium exceeded the published ceiling.",
        )
        second = cancel_pending_signal(
            signal_id=signal.pk,
            note="This retry must not create another event or customer alert.",
        )

        self.assertFalse(first.already_applied)
        self.assertTrue(second.already_applied)
        self.assertEqual(first.update.pk, second.update.pk)
        self.assertEqual(TradeSignalUpdate.objects.filter(signal=signal, event_type="cancelled").count(), 1)
        self.assertEqual(TelegramNotification.objects.filter(update__signal=signal).count(), 2)

    def test_cancel_refuses_any_setup_with_an_entry_order(self):
        signal = self.signal(paper_entry_order_id="broker-order-1")
        with self.assertRaisesMessage(TradeLifecycleError, "entry or broker order"):
            cancel_pending_signal(
                signal_id=signal.pk,
                note="Cancellation should be refused because this trade has an entry order.",
            )
        signal.refresh_from_db()
        self.assertEqual(signal.status, TradeSignal.STATUS_PUBLISHED)


@override_settings(
    QUANTELLE_RESEARCH_OPERATOR_TOKEN="operator-secret-with-more-than-32-characters",
    QUANTELLE_RESEARCH_OPERATOR_USERNAME="quantelle-research-operator",
)
class TradeLifecycleOperatorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.signal = TradeLifecycleTests.signal(self)
        self.url = reverse("trade-signal-lifecycle-action", args=[self.signal.pk])
        self.payload = {
            "action": "cancel",
            "expected_status": "published",
            "note": "Cancelled before entry because the option exceeded the do-not-chase ceiling.",
        }

    def test_operator_token_cancels_trade_and_provisions_low_privilege_account(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer operator-secret-with-more-than-32-characters")
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "cancelled")
        self.assertEqual(response.data["notification_status"], "pending")
        user = get_user_model().objects.get(username="quantelle-research-operator")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())

    def test_operator_api_rejects_missing_or_wrong_token(self):
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer wrong-token")
        self.assertEqual(self.client.post(self.url, self.payload, format="json").status_code, 403)


@override_settings(
    QUANTELLE_RESEARCH_OPERATOR_TOKEN="operator-secret-with-more-than-32-characters",
    QUANTELLE_RESEARCH_OPERATOR_USERNAME="quantelle-research-operator",
)
class TradePublicationOperatorApiTests(TestCase):
    def setUp(self):
        config_patcher = patch("ranker.trade_lifecycle.load_paper_config")
        self.paper_config = config_patcher.start()
        self.addCleanup(config_patcher.stop)
        self.paper_config.return_value = SimpleNamespace(
            enabled=True,
            base_url="https://paper-api.alpaca.markets",
            api_key="paper-key",
            secret_key="paper-secret",
            max_spread_pct=Decimal("8"),
        )
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Bearer operator-secret-with-more-than-32-characters")
        self.url = reverse("trade-signal-publication")
        today = timezone.localdate()
        self.payload = {
            "request_id": "github-issue-99",
            "symbol": "NVDA",
            "company_name": "NVIDIA Corporation",
            "instrument_type": "call",
            "strike": "240.00",
            "expiration": (today + timedelta(days=30)).isoformat(),
            "risk_level": "high",
            "trigger_direction": "above",
            "underlying_trigger_price": "234.80",
            "trigger_confirmation": "Enter only after price holds above the trigger for the confirmation window.",
            "do_not_chase_price": "9.00",
            "entry_deadline": (today + timedelta(days=3)).isoformat(),
            "official_fill_method": "ask",
            "entry_low": "6.50",
            "entry_high": "8.50",
            "initial_stop": "4.25",
            "target_1": "13.00",
            "target_2": "16.00",
            "thesis": "Relative strength and sustained semiconductor momentum support a confirmed breakout setup.",
            "invalidation": "Cancel before entry if the trigger fails or the option exceeds the published ceiling.",
            "evidence_tags": ["Price action", "Options liquidity", "AI momentum"],
            "paper_quantity": 1,
        }

    @staticmethod
    def snapshot(signal):
        signal.publication_quote_source = "Test quote"
        signal.publication_quote_at = timezone.now()
        signal.publication_underlying_price = Decimal("233.50")
        signal.publication_option_bid = Decimal("6.80")
        signal.publication_option_ask = Decimal("6.90")
        signal.publication_option_midpoint = Decimal("6.85")
        signal.publication_option_spread_pct = Decimal("1.46")
        signal.publication_option_volume = 100
        signal.publication_option_open_interest = 1000
        return True

    @patch("ranker.trade_lifecycle.apply_publication_snapshot")
    def test_publish_creates_one_paper_managed_public_signal_and_is_idempotent(self, snapshot):
        snapshot.side_effect = self.snapshot

        first = self.client.post(self.url, self.payload, format="json")
        second = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.data["already_applied"])
        self.assertTrue(second.data["already_applied"])
        self.assertEqual(first.data["signal_id"], second.data["signal_id"])
        signal = TradeSignal.objects.get(operator_request_id="github-issue-99")
        self.assertEqual(signal.status, TradeSignal.STATUS_PUBLISHED)
        self.assertTrue(signal.paper_execution_enabled)
        self.assertEqual(signal.paper_quantity, 1)
        self.assertEqual(signal.current_stop, Decimal("4.25"))
        self.assertEqual(signal.updates.filter(event_type="published").count(), 1)
        self.assertEqual(TelegramNotification.objects.filter(update__signal=signal).count(), 1)
        self.assertEqual(snapshot.call_count, 1)

    @patch("ranker.trade_lifecycle.apply_publication_snapshot")
    def test_publish_blocks_quote_above_do_not_chase_ceiling(self, snapshot):
        def expensive_snapshot(signal):
            self.snapshot(signal)
            signal.publication_option_ask = Decimal("9.50")
            return True

        snapshot.side_effect = expensive_snapshot
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertIn("do-not-chase", response.data["detail"])
        self.assertFalse(TradeSignal.objects.filter(operator_request_id="github-issue-99").exists())

    def test_publish_rejects_non_one_contract_or_invalid_trade_plan(self):
        self.payload["paper_quantity"] = 2
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("paper_quantity", response.data)

        self.payload["paper_quantity"] = 1
        self.payload["initial_stop"] = "7.00"
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("initial_stop", response.data)
