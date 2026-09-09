"""Small, paper-only Alpaca client used by the published-signal executor."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os

import requests


PAPER_API_URL = "https://paper-api.alpaca.markets"


class PaperTradingError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperConfig:
    enabled: bool
    api_key: str
    secret_key: str
    base_url: str
    data_url: str
    stock_feed: str
    option_feed: str
    max_open_positions: int
    max_spread_pct: Decimal
    confirm_seconds: int
    max_quote_age_seconds: int


def load_paper_config():
    return PaperConfig(
        enabled=os.getenv("ALPACA_PAPER_EXECUTION_ENABLED", "false").lower() == "true",
        api_key=os.getenv("ALPACA_PAPER_API_KEY", ""),
        secret_key=os.getenv("ALPACA_PAPER_SECRET_KEY", ""),
        base_url=os.getenv("ALPACA_PAPER_BASE_URL", PAPER_API_URL).rstrip("/"),
        data_url=os.getenv("ALPACA_PAPER_DATA_URL", "https://data.alpaca.markets").rstrip("/"),
        stock_feed=os.getenv("ALPACA_PAPER_STOCK_FEED", "iex"),
        option_feed=os.getenv("ALPACA_PAPER_OPTION_FEED", "indicative"),
        max_open_positions=int(os.getenv("ALPACA_PAPER_MAX_OPEN_POSITIONS", "2")),
        max_spread_pct=Decimal(os.getenv("ALPACA_PAPER_MAX_SPREAD_PCT", "8")),
        confirm_seconds=int(os.getenv("ALPACA_PAPER_CONFIRM_SECONDS", "60")),
        max_quote_age_seconds=int(os.getenv("ALPACA_PAPER_MAX_QUOTE_AGE_SECONDS", "30")),
    )


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class AlpacaPaperClient:
    def __init__(self):
        self.config = load_paper_config()
        self.base_url = self.config.base_url
        self.data_url = self.config.data_url
        if self.base_url != PAPER_API_URL:
            raise PaperTradingError("Refusing execution: Alpaca base URL is not the paper endpoint")
        if not self.config.api_key or not self.config.secret_key:
            raise PaperTradingError("Alpaca paper credentials are not configured")
        self.headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.secret_key,
        }

    def _request(self, method, url, **kwargs):
        response = requests.request(method, url, headers=self.headers, timeout=12, **kwargs)
        if response.status_code >= 400:
            detail = response.text[:200]
            raise PaperTradingError(f"Alpaca returned {response.status_code}: {detail}")
        return response.json()

    def _require_fresh_quote(self, timestamp):
        if not timestamp:
            raise PaperTradingError("Quote has no timestamp")
        try:
            stamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            raise PaperTradingError("Quote timestamp is invalid")
        if age < -5 or age > self.config.max_quote_age_seconds:
            raise PaperTradingError(f"Quote is stale ({max(0, int(age))} seconds old)")

    def clock(self):
        return self._request("GET", f"{self.base_url}/v2/clock")

    def order(self, order_id):
        return self._request("GET", f"{self.base_url}/v2/orders/{order_id}")

    def submit_limit_order(self, *, symbol, quantity, side, limit_price, client_order_id):
        intent = "buy_to_open" if side == "buy" else "sell_to_close"
        return self._request(
            "POST",
            f"{self.base_url}/v2/orders",
            json={
                "symbol": symbol,
                "qty": str(quantity),
                "side": side,
                "type": "limit",
                "time_in_force": "day",
                "limit_price": str(limit_price),
                "client_order_id": client_order_id,
                "position_intent": intent,
            },
        )

    def stock_quote(self, symbol):
        payload = self._request(
            "GET",
            f"{self.data_url}/v2/stocks/{symbol}/quotes/latest",
            params={"feed": self.config.stock_feed},
        )
        quote = payload.get("quote") or {}
        self._require_fresh_quote(quote.get("t"))
        bid, ask = _decimal(quote.get("bp")), _decimal(quote.get("ap"))
        if bid is None or ask is None or ask <= 0:
            raise PaperTradingError(f"No executable stock quote for {symbol}")
        return {"bid": bid, "ask": ask, "midpoint": (bid + ask) / 2, "timestamp": quote.get("t")}

    def option_quote(self, contract_symbol):
        payload = self._request(
            "GET",
            f"{self.data_url}/v1beta1/options/quotes/latest",
            params={"symbols": contract_symbol, "feed": self.config.option_feed},
        )
        quote = (payload.get("quotes") or {}).get(contract_symbol) or {}
        self._require_fresh_quote(quote.get("t"))
        bid, ask = _decimal(quote.get("bp")), _decimal(quote.get("ap"))
        if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
            raise PaperTradingError(f"No executable option quote for {contract_symbol}")
        midpoint = (bid + ask) / 2
        spread_pct = ((ask - bid) / midpoint) * 100 if midpoint else Decimal("999")
        return {
            "bid": bid,
            "ask": ask,
            "midpoint": midpoint,
            "spread_pct": spread_pct,
            "timestamp": quote.get("t"),
        }
