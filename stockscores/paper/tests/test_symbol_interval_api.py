import pandas as pd
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from paper.api.views import SymbolIntervalView


class SymbolIntervalApiTests(TestCase):
    @patch("paper.api.views.yf")
    def test_returns_last_close_and_candles(self, mock_yf):
        index = pd.date_range("2024-01-01", periods=3, freq="1min")
        df = pd.DataFrame(
            {
                "Open": [1.0, 2.0, 3.0],
                "High": [1.2, 2.2, 3.2],
                "Low": [0.9, 1.9, 2.9],
                "Close": [1.1, 2.1, 3.1],
                "Volume": [100, 200, 300],
            },
            index=index,
        )
        mock_yf.download.return_value = df
        view = SymbolIntervalView.as_view()
        req = APIRequestFactory().get("/api/paper/symbols/AAPL/interval/?interval=1m&period=max")
        resp = view(req, symbol="AAPL")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["symbol"], "AAPL")
        self.assertEqual(resp.data["last_close"], 3.1)
        self.assertEqual(len(resp.data["candles"]), 3)
        mock_yf.download.assert_called_with("AAPL", period="max", interval="1m", progress=False)

    def test_rejects_bad_interval(self):
        view = SymbolIntervalView.as_view()
        req = APIRequestFactory().get("/api/paper/symbols/AAPL/interval/?interval=10h")
        resp = view(req, symbol="AAPL")
        self.assertEqual(resp.status_code, 400)
