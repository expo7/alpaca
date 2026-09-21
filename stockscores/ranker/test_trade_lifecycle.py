from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
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

