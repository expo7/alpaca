"""Recovery regressions: independent quotes and enforceable premium ceilings."""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from .models import TradeSignal
from .trade_quotes import get_trade_signal_quote, apply_publication_snapshot
from .tasks import _process_published_signal
from .alpaca_paper import PaperTradingError


class RecoveryTests(TestCase):
    def signal(self, **kwargs):
        values = dict(symbol="IWM", instrument_type="call", strike=Decimal("250"),
                      expiration=date(2026, 11, 20), entry_low=Decimal("2"),
                      entry_high=Decimal("3"), do_not_chase_price=Decimal("250"),
                      initial_stop=Decimal("1"), target_1=Decimal("4"),
                      underlying_trigger_price=Decimal("240"), trigger_direction="above",
                      trigger_first_seen_at=timezone.now()-timedelta(minutes=3),
                      status=TradeSignal.STATUS_PUBLISHED)
        values.update(kwargs)
        return TradeSignal.objects.create(**values)

    @patch("ranker.trade_quotes.AlpacaPaperClient")
    def test_option_quote_survives_underlying_and_metadata_failure(self, cls):
        signal = self.signal()
        stamp = timezone.now().isoformat()
        client = cls.return_value
        client.config.option_feed = "indicative"
        client.option_quote.return_value = dict(bid=2.40, ask=2.50, midpoint=2.45,
                                               spread_pct=4.08, timestamp=stamp)
        client.stock_quote.side_effect = PaperTradingError("unavailable")
        client.option_reference.side_effect = PaperTradingError("unavailable")
        with patch.dict("sys.modules", {"yfinance": None}):
            quote = get_trade_signal_quote(signal, use_cache=False)
        self.assertTrue(quote["available"])
        self.assertEqual(quote["option_ask"], 2.5)
        self.assertEqual(quote["option_quote_at"], stamp)
        self.assertIsNone(quote["underlying_price"])
        self.assertIsNone(quote["option_open_interest"])
        self.assertEqual(quote["source"], "Alpaca indicative (modified)")

    @patch("ranker.trade_quotes.AlpacaPaperClient")
    def test_yahoo_fallback_after_primary_failure(self, cls):
        signal = self.signal()
        cls.return_value.option_quote.side_effect = PaperTradingError("primary unavailable")
        import pandas as pd
        ticker = Mock()
        ticker.option_chain.return_value = SimpleNamespace(calls=pd.DataFrame([dict(strike=250, bid=2.4, ask=2.5, lastPrice=2.45, volume=800, openInterest=1200)]))
        fake_yf = SimpleNamespace(Ticker=Mock(return_value=ticker))
        with patch.dict("sys.modules", {"yfinance": fake_yf}), patch("ranker.trade_quotes._latest_underlying", return_value=(250, timezone.now())):
            quote = get_trade_signal_quote(signal, use_cache=False)
        self.assertTrue(quote["available"])
        self.assertEqual(quote["source"], "Yahoo Finance (delayed)")
        self.assertEqual(quote["option_ask"], 2.5)
        self.assertEqual(quote["primary_error"], "PaperTradingError")

    def test_entry_high_still_blocks_legacy_underlying_scale_no_chase(self):
        signal = self.signal()
        client = Mock()
        client.stock_quote.return_value = {"midpoint": Decimal("241")}
        client.option_quote.return_value = {"ask": Decimal("3.10"), "spread_pct": Decimal("3")}
        config = SimpleNamespace(confirm_seconds=60, max_spread_pct=8, max_open_positions=2)
        outcome = _process_published_signal(signal, client, timezone.now(), config)
        self.assertEqual(outcome, "premium_outside_entry_range")
        client.submit_limit_order.assert_not_called()

    @patch("ranker.trade_quotes.get_trade_signal_quote")
    def test_publication_preserves_option_quote_timestamp(self, quote):
        stamp = timezone.now()-timedelta(seconds=12)
        quote.return_value = dict(available=True, source="Alpaca indicative (modified)",
                                 option_quote_at=stamp.isoformat(), option_bid=2.4, option_ask=2.5)
        signal = self.signal()
        apply_publication_snapshot(signal)
        self.assertEqual(signal.publication_quote_at, stamp)
