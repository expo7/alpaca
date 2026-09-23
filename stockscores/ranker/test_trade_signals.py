from decimal import Decimal
from datetime import date
from unittest.mock import patch

from django.urls import reverse
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import TradeSignal, TradeSignalUpdate
from .trade_quotes import get_paper_position


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

    def test_public_feed_excludes_drafts_and_includes_completed_updates(self):
        published = self._signal(status=TradeSignal.STATUS_CLOSED)
        self._signal(symbol="AAPL", status=TradeSignal.STATUS_DRAFT)
        self._signal(symbol="TEST", status=TradeSignal.STATUS_CLOSED, is_test=True)
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
        self.assertEqual(response.data[0]["instrument"], "MU 110.00C 9/18/26")
        self.assertEqual(response.data[0]["contract_symbol"], "MU260918C00110000")
        target_updates = [update for update in response.data[0]["updates"] if update["event_type"] == "target"]
        self.assertEqual(target_updates[0]["note"], "First target reached.")

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
    def test_completed_quote_endpoint_remains_public(self, get_quote):
        signal = self._signal(status=TradeSignal.STATUS_CLOSED)
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

    @patch("ranker.trade_quotes.AlpacaPaperClient")
    def test_open_executed_signal_reports_paper_position(self, client_class):
        signal = self._signal(
            status=TradeSignal.STATUS_OPEN,
            paper_execution_enabled=True,
            paper_entry_order_id="paper-order-1",
        )
        client_class.return_value.position.return_value = {
            "qty": "1",
            "avg_entry_price": "2.91",
            "current_price": "3.20",
            "market_value": "320.00",
            "cost_basis": "291.00",
            "unrealized_pl": "29.00",
            "unrealized_plpc": "0.09965636",
        }

        position = get_paper_position(signal, use_cache=False)

        self.assertTrue(position["available"])
        self.assertEqual(position["unrealized_pl"], 29.0)
        self.assertEqual(position["unrealized_pl_pct"], 9.97)
        client_class.return_value.position.assert_called_once_with(signal.contract_symbol)

    @patch("ranker.views.get_paper_position")
    @patch("ranker.views.get_trade_signal_quote")
    def test_closed_market_quote_uses_alpaca_position_mark(self, get_quote, get_position):
        signal = self._signal(
            status=TradeSignal.STATUS_OPEN,
            paper_execution_enabled=True,
            paper_entry_order_id="paper-order-1",
        )
        get_quote.return_value = {
            "available": True,
            "status": "market_closed",
            "status_label": "Market closed · last available",
            "option_bid": None,
            "option_ask": None,
            "option_midpoint": None,
            "option_last": 3.10,
        }
        get_position.return_value = {
            "available": True,
            "current_price": 3.20,
            "unrealized_pl": 29.0,
        }

        response = self.client.get(reverse("trade-signal-quote", args=[signal.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["option_midpoint"], 3.20)
        self.assertEqual(response.data["option_price_label"], "Alpaca position mark")
        self.assertTrue(response.data["option_price_is_fallback"])
