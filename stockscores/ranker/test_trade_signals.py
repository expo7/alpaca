from decimal import Decimal
from datetime import date
from unittest.mock import patch

from django.urls import reverse
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import TradeSignal, TradeSignalUpdate


class TradeSignalApiTests(APITestCase):
    def _signal(self, **overrides):
        data = {
            "symbol": "mu",
            "instrument_type": "call",
            "strike": Decimal("110"),
            "expiration": date(2026, 9, 18),
            "status": TradeSignal.STATUS_PUBLISHED,
            "entry_low": Decimal("12.30"),
            "initial_stop": Decimal("9.80"),
            "target_1": Decimal("14.15"),
            "thesis": "Price action and volume support the setup.",
        }
        data.update(overrides)
        return TradeSignal.objects.create(**data)

    def test_public_feed_excludes_drafts_and_includes_updates(self):
        published = self._signal()
        self._signal(symbol="AAPL", status=TradeSignal.STATUS_DRAFT)
        TradeSignalUpdate.objects.create(
            signal=published,
            event_type="target",
            note="First target reached.",
            price=Decimal("14.15"),
        )

        response = self.client.get(reverse("trade-signal-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["symbol"], "MU")
        self.assertEqual(response.data[0]["instrument"], "MU 110C 9/18/26")
        self.assertEqual(response.data[0]["contract_symbol"], "MU260918C00110000")
        self.assertEqual(response.data[0]["updates"][0]["note"], "First target reached.")

    def test_publishing_sets_an_immutable_initial_timestamp(self):
        signal = self._signal(status=TradeSignal.STATUS_DRAFT)
        self.assertIsNone(signal.published_at)

        signal.status = TradeSignal.STATUS_PUBLISHED
        signal.save()
        first_published_at = signal.published_at
        signal.status = TradeSignal.STATUS_OPEN
        signal.save()

        self.assertIsNotNone(first_published_at)
        self.assertEqual(signal.published_at, first_published_at)

        signal.entry_low = Decimal("1.00")
        with self.assertRaises(ValidationError):
            signal.save()

    def test_updates_are_append_only(self):
        update = TradeSignalUpdate.objects.create(signal=self._signal(), note="Original update")
        update.note = "Rewritten update"
        with self.assertRaises(ValidationError):
            update.save()

    @patch("ranker.views.get_trade_signal_quote")
    def test_public_quote_endpoint(self, get_quote):
        signal = self._signal()
        get_quote.return_value = {
            "available": True,
            "status": "delayed",
            "status_label": "Delayed quote",
            "underlying_price": 1016.59,
            "option_bid": 34.90,
            "option_ask": 37.00,
        }

        response = self.client.get(reverse("trade-signal-quote", args=[signal.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["option_ask"], 37.00)
