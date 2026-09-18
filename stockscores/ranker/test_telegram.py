from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from .models import TelegramNotification, TradeSignal, TradeSignalUpdate
from .telegram import deliver_telegram_notification, format_trade_update


class TelegramNotificationTests(TestCase):
    def signal(self, **overrides):
        values = {
            "symbol": "AMZN",
            "company_name": "Amazon",
            "instrument_type": "call",
            "strike": Decimal("240"),
            "expiration": "2026-10-16",
            "status": TradeSignal.STATUS_DRAFT,
            "risk_level": "moderate",
            "trigger_direction": "above",
            "underlying_trigger_price": Decimal("235"),
            "entry_low": Decimal("6.50"),
            "entry_high": Decimal("7.00"),
            "initial_stop": Decimal("4.25"),
            "target_1": Decimal("13.00"),
            "thesis": "Test setup",
        }
        values.update(overrides)
        return TradeSignal.objects.create(**values)

    def test_publication_creates_one_immutable_event_and_outbox_entry(self):
        signal = self.signal()
        signal.status = TradeSignal.STATUS_PUBLISHED
        signal.save()

        publication = TradeSignalUpdate.objects.get(signal=signal, event_type="published")
        self.assertEqual(publication.telegram_notification.status, TelegramNotification.STATUS_PENDING)

        signal.refresh_from_db()
        signal.company_name = "Amazon"
        signal.save(update_fields=["company_name", "updated_at"])
        self.assertEqual(
            TradeSignalUpdate.objects.filter(signal=signal, event_type="published").count(),
            1,
        )

    def test_each_update_has_only_one_outbox_entry(self):
        signal = self.signal()
        update = TradeSignalUpdate.objects.create(
            signal=signal,
            event_type="note",
            note="A useful lifecycle note.",
        )
        TelegramNotification.objects.get_or_create(update=update)
        self.assertEqual(TelegramNotification.objects.filter(update=update).count(), 1)

    def test_formatter_includes_actionable_prices_and_eastern_timestamp(self):
        signal = self.signal(status=TradeSignal.STATUS_PUBLISHED)
        update = TradeSignalUpdate.objects.get(signal=signal, event_type="published")

        message = format_trade_update(update)

        self.assertIn("New Trade Setup", message)
        self.assertIn("AMZN 240.00C", message)
        self.assertIn("$6.50–$7.00", message)
        self.assertIn("$4.25", message)
        self.assertIn("$13.00", message)
        self.assertIn(" ET", message)
        self.assertIn(f"https://quantelle.io/signals#trade-{signal.pk}", message)
        self.assertIn("View this trade on Quantelle", message)

    @override_settings(
        TELEGRAM_NOTIFICATIONS_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHAT_ID="-100123",
    )
    @patch("ranker.telegram.requests.post")
    def test_delivery_marks_outbox_sent(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True, "result": {"message_id": 42}}
        post.return_value = response
        signal = self.signal()
        update = TradeSignalUpdate.objects.create(
            signal=signal,
            event_type="triggered",
            note="Filled at the official price.",
            price=Decimal("6.88"),
        )
        notification = update.telegram_notification

        result = deliver_telegram_notification.run(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(notification.status, TelegramNotification.STATUS_SENT)
        self.assertEqual(notification.telegram_message_id, 42)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["chat_id"], "-100123")
        self.assertIn("$6.88", payload["text"])

    @override_settings(
        TELEGRAM_NOTIFICATIONS_ENABLED=True,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHAT_ID="-100123",
    )
    @patch("ranker.telegram.requests.post")
    def test_duplicate_queued_delivery_does_not_send_twice(self, post):
        signal = self.signal()
        update = TradeSignalUpdate.objects.create(
            signal=signal,
            event_type="note",
            note="Only send this once.",
        )
        notification = update.telegram_notification
        notification.status = TelegramNotification.STATUS_SENDING
        notification.save(update_fields=["status", "updated_at"])

        result = deliver_telegram_notification.run(notification.pk)

        self.assertEqual(result["status"], "already_sending")
        post.assert_not_called()

    @override_settings(
        TELEGRAM_NOTIFICATIONS_ENABLED=False,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHAT_ID="-100123",
    )
    @patch("ranker.telegram.requests.post")
    def test_disabled_delivery_leaves_notification_pending(self, post):
        signal = self.signal()
        update = TradeSignalUpdate.objects.create(
            signal=signal,
            event_type="note",
            note="Do not send yet.",
        )

        result = deliver_telegram_notification.run(update.telegram_notification.pk)

        self.assertEqual(result["status"], "disabled")
        post.assert_not_called()
        update.telegram_notification.refresh_from_db()
        self.assertEqual(update.telegram_notification.status, TelegramNotification.STATUS_PENDING)
