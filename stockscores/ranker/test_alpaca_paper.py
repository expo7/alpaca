import os
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .alpaca_paper import AlpacaPaperClient


PAPER_ENV = {
    "ALPACA_PAPER_API_KEY": "paper-key",
    "ALPACA_PAPER_SECRET_KEY": "paper-secret",
    "ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
}


class AlpacaPaperOrderTests(SimpleTestCase):
    @patch.dict(os.environ, PAPER_ENV)
    @patch("ranker.alpaca_paper.requests.request")
    def test_stop_order_is_single_leg_sell_to_close_gtc(self, request):
        response = Mock(status_code=200, content=b"{}")
        response.json.return_value = {"id": "stop-1", "status": "accepted"}
        request.return_value = response

        client = AlpacaPaperClient()
        client.submit_stop_order(
            symbol="NVDA261016C00240000",
            quantity=1,
            stop_price=Decimal("4.25"),
            client_order_id="quantelle-7-stop-1",
        )

        request.assert_called_once_with(
            "POST",
            "https://paper-api.alpaca.markets/v2/orders",
            headers=client.headers,
            timeout=12,
            json={
                "symbol": "NVDA261016C00240000",
                "qty": "1",
                "side": "sell",
                "type": "stop",
                "time_in_force": "gtc",
                "stop_price": "4.25",
                "client_order_id": "quantelle-7-stop-1",
                "position_intent": "sell_to_close",
            },
        )

    @patch.dict(os.environ, PAPER_ENV)
    @patch("ranker.alpaca_paper.requests.request")
    def test_cancel_accepts_empty_204_response(self, request):
        request.return_value = Mock(status_code=204, content=b"")

        client = AlpacaPaperClient()

        self.assertEqual(client.cancel_order("stop-1"), {})
