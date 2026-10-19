from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch
from dataclasses import replace
from .alpaca_paper import AlpacaPaperClient, PaperTradingError, PAPER_API_URL, load_paper_config


class PaperDataFallbackTests(TestCase):
    def setUp(self):
        self.client = object.__new__(AlpacaPaperClient)
        self.client.config = replace(load_paper_config(), stock_feed="iex", max_quote_age_seconds=30)
        self.client.base_url = PAPER_API_URL
        self.client.data_url = "https://data.alpaca.markets"

    def quote(self, age, bid=100, ask=101):
        return {"quote": {"t": (datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(), "bp": bid, "ap": ask}}

    def test_main_paper_falls_back_preserving_timestamp(self):
        delayed = self.quote(901)
        with patch.object(self.client, "_request", side_effect=[self.quote(1000), delayed]) as request:
            result = self.client.stock_quote("IWM", allow_delayed=True)
        self.assertEqual(result["timestamp"], delayed["quote"]["t"])
        self.assertEqual(result["source"], "delayed_sip")
        self.assertTrue(result["delayed"])
        self.assertEqual(request.call_args.kwargs["params"], {"feed": "delayed_sip"})

    def test_strict_default_does_not_fallback(self):
        with patch.object(self.client, "_request", return_value=self.quote(901)) as request:
            with self.assertRaises(PaperTradingError):
                self.client.stock_quote("IWM")
        self.assertEqual(request.call_count, 1)

    def test_obsolete_future_crossed_and_nonfinite_data_rejected(self):
        for bad in [self.quote(1201), self.quote(-60), self.quote(901, 102, 101), self.quote(901, float('nan'), 101)]:
            with self.subTest(bad=bad), patch.object(self.client, "_request", side_effect=[self.quote(1000), bad]):
                with self.assertRaises(PaperTradingError):
                    self.client.stock_quote("IWM", allow_delayed=True)

    def test_option_freshness_remains_strict(self):
        with self.assertRaises(PaperTradingError):
            self.client._require_fresh_quote(self.quote(901)["quote"]["t"])

    def test_fresh_primary_avoids_extra_request(self):
        with patch.object(self.client, "_request", return_value=self.quote(1)) as request:
            self.assertFalse(self.client.stock_quote("IWM", allow_delayed=True)["delayed"])
        self.assertEqual(request.call_count, 1)
