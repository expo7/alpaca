from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, Callable, Iterable, Optional

from django.conf import settings
from django.utils.module_loading import import_string

import pandas as pd
import yfinance as yf
from paper.models import Instrument
from ranker.metrics import increment_yf_counter


@dataclass
class Quote:
    symbol: str
    price: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...

    def get_history(
        self, symbol: str, start, end, interval: str = "1d"
    ) -> pd.DataFrame: ...

    def get_history_period(
        self, symbol: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame: ...

    def subscribe(
        self, symbols: Iterable[str], callback: Callable[[Quote], None]
    ) -> None: ...


def _ensure_instrument(symbol: str) -> Instrument:
    sym = symbol.upper()
    inst, _ = Instrument.objects.get_or_create(symbol=sym, defaults={"asset_class": "equity"})
    return inst


class YFinanceMarketDataProvider:
    """
    Lightweight adapter around yfinance. This is intentionally simple for now –
    later we can swap in Polygon/IEX/etc. without touching the execution engine.
    """

    def __init__(self):
        self._client = yf

    def get_quote(self, symbol: str) -> Quote:
        _ensure_instrument(symbol)
        increment_yf_counter()
        ticker = self._client.Ticker(symbol)
        info = ticker.fast_info
        price = float(info.last_price) if getattr(info, "last_price", None) else None
        if price is None:
            hist = ticker.history(period="1d", interval="1m")
            if hist.empty:
                raise ValueError(f"No price data for {symbol}")
            last = hist.iloc[-1]
            price = float(last["Close"])
        return Quote(
            symbol=symbol.upper(),
            price=price,
            timestamp=datetime.utcnow(),
            bid=float(info.bid) if getattr(info, "bid", None) else None,
            ask=float(info.ask) if getattr(info, "ask", None) else None,
            open=float(info.open) if getattr(info, "open", None) else None,
            high=float(info.day_high) if getattr(info, "day_high", None) else None,
            low=float(info.day_low) if getattr(info, "day_low", None) else None,
            close=float(info.previous_close)
            if getattr(info, "previous_close", None)
            else None,
            volume=float(info.volume) if getattr(info, "volume", None) else None,
        )

    def get_history(
        self, symbol: str, start, end, interval: str = "1d"
    ) -> pd.DataFrame:
        increment_yf_counter()
        ticker = self._client.Ticker(symbol)
        df = ticker.history(start=start, end=end, interval=interval)
        return df

    def get_history_period(
        self, symbol: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        increment_yf_counter()
        ticker = self._client.Ticker(symbol)
        return ticker.history(period=period, interval=interval)

    def subscribe(
        self, symbols: Iterable[str], callback: Callable[[Quote], None]
    ) -> None:
        # For now, we don't maintain persistent subscriptions; callers can
        # schedule periodic polling.
        for sym in symbols:
            try:
                callback(self.get_quote(sym))
            except Exception:
                continue


_provider_instance: Optional[MarketDataProvider] = None


def get_market_data_provider() -> MarketDataProvider:
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance
    provider_path = getattr(
        settings,
        "PAPER_MARKET_DATA_PROVIDER",
        "paper.services.market_data.YFinanceMarketDataProvider",
    )
    ProviderCls = import_string(provider_path)
    base_provider = ProviderCls()
    mode = getattr(settings, "PAPER_MARKET_DATA_MODE", "live").lower()
    if mode == "delayed":
        base_provider = DelayedMarketDataProvider(base_provider)
    _provider_instance = base_provider
    return _provider_instance


class DelayedMarketDataProvider:
    """
    Wrapper that returns delayed prices (prev close) and stamps timestamp at prior close.
    """

    def __init__(self, base: MarketDataProvider):
        self.base = base

    def get_quote(self, symbol: str) -> Quote:
        q = self.base.get_quote(symbol)
        price = q.close if q.close is not None else q.price
        ts = q.timestamp - timedelta(hours=16) if q.timestamp else datetime.utcnow()
        return Quote(
            symbol=q.symbol,
            price=price,
            timestamp=ts,
            bid=q.bid,
            ask=q.ask,
            open=q.open,
            high=q.high,
            low=q.low,
            close=q.close,
            volume=q.volume,
        )

    def get_history(self, *args, **kwargs):
        return self.base.get_history(*args, **kwargs)

    def get_history_period(self, *args, **kwargs):
        return self.base.get_history_period(*args, **kwargs)

    def subscribe(self, symbols: Iterable[str], callback: Callable[[Quote], None]) -> None:
        return self.base.subscribe(symbols, callback)
