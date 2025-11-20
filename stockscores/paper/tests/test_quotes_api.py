from django.test import TestCase
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from paper.api.views import QuoteView
from paper.services.market_data import Quote


class QuotesApiTests(TestCase):
    @patch("paper.api.views.get_market_data_provider")
    def test_returns_quotes(self, mock_provider):
        class FakeProvider:
            def get_quote(self, symbol):
                return Quote(symbol=symbol, price=123.4, timestamp=None)

        mock_provider.return_value = FakeProvider()
        view = QuoteView.as_view()
        req = APIRequestFactory().get("/api/paper/quotes/?symbols=AAPL,MSFT")
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]["symbol"], "AAPL")
