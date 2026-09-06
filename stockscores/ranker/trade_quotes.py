"""Best-effort delayed quotes for published trade records."""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.utils import timezone
import yfinance as yf


QUOTE_SOURCE = "Yahoo Finance (delayed)"
QUOTE_CACHE_SECONDS = 90


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return round(number, 4)


def _integer(value):
    number = _number(value)
    return int(number) if number is not None and number >= 0 else None


def _decimal(value):
    number = _number(value)
    if number is None:
        return None
    try:
        return Decimal(str(number)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _latest_underlying(ticker):
    history = ticker.history(period="1d", interval="1m", prepost=True, auto_adjust=False)
    if history is None or history.empty:
        return None, None
    closes = history.get("Close")
    if closes is None:
        return None, None
    closes = closes.dropna()
    if closes.empty:
        return None, None
    stamp = closes.index[-1]
    if hasattr(stamp, "to_pydatetime"):
        stamp = stamp.to_pydatetime()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt_timezone.utc)
    return _number(closes.iloc[-1]), stamp.astimezone(dt_timezone.utc)


def get_trade_signal_quote(signal, use_cache=True):
    cache_key = f"trade-signal-quote-v1:{signal.pk}:{signal.updated_at.timestamp() if signal.updated_at else 0}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    fetched_at = timezone.now()
    result = {
        "available": False,
        "status": "unavailable",
        "status_label": "Quote unavailable",
        "source": QUOTE_SOURCE,
        "fetched_at": fetched_at.isoformat(),
        "underlying_price": None,
        "option_bid": None,
        "option_ask": None,
        "option_midpoint": None,
        "option_last": None,
        "option_volume": None,
        "option_open_interest": None,
        "spread_pct": None,
    }

    try:
        ticker = yf.Ticker(signal.symbol)
        underlying_price, market_stamp = _latest_underlying(ticker)
        result["underlying_price"] = underlying_price

        if signal.instrument_type != "stock":
            if not signal.expiration or signal.strike is None:
                raise ValueError("Option contract is incomplete")
            chain = ticker.option_chain(signal.expiration.isoformat())
            table = chain.calls if signal.instrument_type == "call" else chain.puts
            matches = table[(table["strike"] - float(signal.strike)).abs() < 0.001]
            if matches.empty:
                raise ValueError("Contract was not found in the current chain")
            row = matches.iloc[0]
            bid = _number(row.get("bid"))
            ask = _number(row.get("ask"))
            midpoint = round((bid + ask) / 2, 4) if bid is not None and ask is not None else None
            spread_pct = round(((ask - bid) / midpoint) * 100, 2) if midpoint and ask >= bid else None
            result.update(
                option_bid=bid,
                option_ask=ask,
                option_midpoint=midpoint,
                option_last=_number(row.get("lastPrice")),
                option_volume=_integer(row.get("volume")),
                option_open_interest=_integer(row.get("openInterest")),
                spread_pct=spread_pct,
            )

        age_seconds = (fetched_at - market_stamp).total_seconds() if market_stamp else None
        if age_seconds is not None and age_seconds > 45 * 60:
            result["status"] = "market_closed"
            result["status_label"] = "Market closed · last available"
        else:
            result["status"] = "delayed"
            result["status_label"] = "Delayed quote"
        result["market_quote_at"] = market_stamp.isoformat() if market_stamp else None
        result["available"] = underlying_price is not None or result["option_bid"] is not None or result["option_ask"] is not None
    except Exception as exc:
        result["error"] = str(exc)[:160]

    cache.set(cache_key, result, QUOTE_CACHE_SECONDS)
    return result


def apply_publication_snapshot(signal):
    """Populate any blank publication quote fields without blocking publication."""
    quote = get_trade_signal_quote(signal, use_cache=False)
    signal.publication_quote_source = quote.get("source") or QUOTE_SOURCE
    if not quote.get("available"):
        return False
    signal.publication_quote_at = timezone.now()
    signal.publication_underlying_price = _decimal(quote.get("underlying_price"))
    signal.publication_option_bid = _decimal(quote.get("option_bid"))
    signal.publication_option_ask = _decimal(quote.get("option_ask"))
    signal.publication_option_midpoint = _decimal(quote.get("option_midpoint"))
    signal.publication_option_spread_pct = _decimal(quote.get("spread_pct"))
    signal.publication_option_volume = quote.get("option_volume")
    signal.publication_option_open_interest = quote.get("option_open_interest")
    return True
