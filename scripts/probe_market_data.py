"""Read-only production market-data probe. Never submits or changes orders."""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

contract = sys.argv[1] if len(sys.argv) > 1 else "QQQ261120P00738000"
match = re.fullmatch(r"([A-Z]{1,6})(\d{6})([CP])(\d{8})", contract)
if not match:
    raise SystemExit("Invalid OCC contract symbol")
symbol, date, kind, strike_raw = match.groups()
expiry = datetime.strptime(date, "%y%m%d").date().isoformat()
strike = int(strike_raw) / 1000
headers = {
    "APCA-API-KEY-ID": os.environ["ALPACA_PAPER_API_KEY"],
    "APCA-API-SECRET-KEY": os.environ["ALPACA_PAPER_SECRET_KEY"],
}
data_url = os.environ.get("ALPACA_PAPER_DATA_URL", "https://data.alpaca.markets").rstrip("/")
paper_url = os.environ.get("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")
if paper_url != "https://paper-api.alpaca.markets" or data_url != "https://data.alpaca.markets":
    raise SystemExit("Unexpected API endpoint; refusing probe")
failures = []

def probe(label, url, params=None, summarize=None):
    for attempt in range(2):
        started = time.monotonic()
        try:
            response = requests.get(url, headers=headers, params=params, timeout=(5, 15))
            result = {"test": label, "attempt": attempt + 1, "http": response.status_code,
                      "elapsed_seconds": round(time.monotonic() - started, 3),
                      "at": datetime.now(timezone.utc).isoformat(),
                      "retry_after": response.headers.get("Retry-After")}
            if response.status_code == 200:
                payload = response.json()
                result["data"] = summarize(payload) if summarize else payload
                print(json.dumps(result), flush=True)
                return payload
            result["error"] = "rate_limit" if response.status_code == 429 else "http_error"
            # No raw server errors, headers, credentials or account payloads in logs.
            print(json.dumps(result), flush=True)
            retryable = response.status_code >= 500
        except (requests.RequestException, ValueError) as exc:
            print(json.dumps({"test": label, "attempt": attempt + 1,
                              "error": type(exc).__name__,
                              "elapsed_seconds": round(time.monotonic() - started, 3)}), flush=True)
            retryable = True
        if not retryable or attempt:
            break
        time.sleep(2)
    failures.append(label)
    return None

clock = probe("clock", paper_url + "/v2/clock")
probe("paper_options_capability", paper_url + "/v2/account",
      summarize=lambda p: {k: p.get(k) for k in
                          ("status", "trading_blocked", "options_approved_level", "options_trading_level", "options_buying_power")})
# One batched discovery request; these are observed symbols, not a claim to
# have screened the entire market. IEX volume/VWAP are venue-specific.
universe = list(dict.fromkeys([symbol, "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMD", "AMZN", "META", "GOOGL", "TSLA", "AVGO", "MU", "INTC", "QCOM", "NFLX", "PLTR", "COIN", "HOOD", "JPM", "BAC", "GS", "XOM", "CVX", "LLY", "UNH", "WMT", "COST", "CAT", "BA", "GE", "SMH", "XLK", "XLF", "XLE", "XLV", "GLD", "TLT"]))
stocks = probe("stock_snapshots", data_url + "/v2/stocks/snapshots",
               {"symbols": ",".join(universe), "feed": "iex"},
               summarize=lambda p: {ticker: {key: row.get(key) for key in
                   ("dailyBar", "prevDailyBar", "minuteBar", "latestTrade")}
                   for ticker, row in p.items()})
stock_quotes = probe("stock_latest_quotes", data_url + "/v2/stocks/quotes/latest",
                     {"symbols": "SPY,QQQ,IWM", "feed": "iex"})
quotes = probe("exact_option_quote", data_url + "/v1beta1/options/quotes/latest",
               {"symbols": contract, "feed": "indicative"})
chain = probe("narrow_option_chain", data_url + "/v1beta1/options/snapshots/" + symbol,
              {"feed": "indicative", "expiration_date": expiry,
               "type": "put" if kind == "P" else "call",
               "strike_price_gte": strike - 1, "strike_price_lte": strike + 1, "limit": 5})
contracts = probe("contract_metadata", paper_url + "/v2/options/contracts/" + contract,
                  summarize=lambda p: {k: p.get(k) for k in
                    ("symbol", "status", "tradable", "expiration_date", "strike_price",
                     "type", "open_interest", "open_interest_date", "close_price", "close_price_date")})
probe("paper_positions_count", paper_url + "/v2/positions",
      summarize=lambda p: {"count": len(p)})
probe("paper_open_orders_count", paper_url + "/v2/orders", {"status": "open", "limit": 500},
      summarize=lambda p: {"count": len(p), "limit": 500})

# Inspect the installed application, not the checkout: production revision
# and image may differ. Never log config objects containing credentials.
try:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockscores.settings")
    import django
    django.setup()
    import hashlib
    import inspect
    from ranker.alpaca_paper import AlpacaPaperClient, load_paper_config
    from ranker.models import TradeExecutorHealth, TradeSignal, TelegramNotification
    from ranker.trade_quotes import get_trade_signal_quote
    config = load_paper_config()
    client = AlpacaPaperClient()
    active = list(TradeSignal.objects.filter(status__in=["published", "open"]).values(
        "id", "symbol", "status", "paper_execution_enabled", "entry_low", "entry_high",
        "initial_stop", "current_stop", "target_1", "entry_deadline", "paper_entry_order_id",
        "paper_exit_order_id", "paper_order_status", "paper_last_error", "paper_last_checked_at",
        "trigger_direction", "underlying_trigger_price", "trigger_first_seen_at", "do_not_chase_price"))
    health = list(TradeExecutorHealth.objects.values(
        "status", "entries_paused", "last_completed_at", "last_success_at", "last_error"))
    runtime = {
        "test": "installed_trade_pipeline", "at": datetime.now(timezone.utc).isoformat(),
        "policy": {key: getattr(config, key) for key in
                   ("enabled", "stock_feed", "option_feed", "max_open_positions",
                    "max_spread_pct", "confirm_seconds", "max_quote_age_seconds")},
        "executor": health, "active_signals": active,
        "recent_signals": list(TradeSignal.objects.order_by("-id").values(
            "id", "symbol", "status", "actual_entry", "final_exit")[:5]),
        "notifications": list(TelegramNotification.objects.order_by("-id").values(
            "id", "update__signal_id", "update__event_type", "status", "sent_at")[:8]),
        "positions": [{key: p.get(key) for key in ("symbol", "qty", "avg_entry_price")}
                      for p in client.positions()],
        "orders": [{key: o.get(key) for key in
                    ("id", "symbol", "side", "qty", "type", "status", "stop_price", "limit_price", "time_in_force")}
                   for o in client.orders() if o.get("status") in
                   ("new", "accepted", "partially_filled", "pending_new", "held", "pending_cancel", "pending_replace")],
        "quote_code_sha256": hashlib.sha256(inspect.getsource(get_trade_signal_quote).encode()).hexdigest(),
    }
    print(json.dumps(runtime, default=str), flush=True)
    if not config.enabled:
        failures.append("paper_execution_disabled")
    if not health or any(row.get("entries_paused") for row in health):
        failures.append("executor_missing_or_entries_paused")
except Exception as exc:
    failures.append("installed_trade_pipeline")
    print(json.dumps({"test": "installed_trade_pipeline", "result": "fail",
                      "error": type(exc).__name__}), flush=True)
quote = ((quotes or {}).get("quotes") or {}).get(contract) or {}
try:
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(quote["t"].replace("Z", "+00:00"))).total_seconds()
    quote_ok = 0 < quote["bp"] <= quote["ap"] and -5 <= age <= 30
except (KeyError, TypeError, ValueError):
    age, quote_ok = None, False
if not quote_ok:
    failures.append("quote_integrity_or_freshness")
if not stocks or any(s not in stocks for s in ("SPY", "QQQ", "IWM")):
    failures.append("missing_index_snapshots")
if not (chain or {}).get("snapshots"):
    failures.append("empty_chain")
stock_ages = {}
for ticker in ("SPY", "QQQ", "IWM"):
    latest = ((stock_quotes or {}).get("quotes") or {}).get(ticker) or {}
    try:
        stock_age = (datetime.now(timezone.utc) - datetime.fromisoformat(latest["t"].replace("Z", "+00:00"))).total_seconds()
        valid = 0 < latest["bp"] <= latest["ap"] and -5 <= stock_age <= 180
    except (KeyError, TypeError, ValueError):
        stock_age, valid = None, False
    stock_ages[ticker] = stock_age
    if not valid:
        failures.append("stale_or_unusable_stock_" + ticker)
print(json.dumps({"stock_quote_ages_seconds": stock_ages}), flush=True)
if any(x.startswith("stale_or_unusable_stock_") for x in failures):
    probe("iex_recent_quote_history", data_url + "/v2/stocks/quotes",
          {"symbols": "SPY,QQQ,IWM", "feed": "iex", "sort": "desc", "limit": 3,
           "start": (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()})
    probe("sip_entitlement_check", data_url + "/v2/stocks/quotes/latest",
          {"symbols": "SPY,QQQ,IWM", "feed": "sip"})
    probe("delayed_sip_check", data_url + "/v2/stocks/quotes/latest",
          {"symbols": "SPY,QQQ,IWM", "feed": "delayed_sip"})
# Exercise the installed primary client through its real GET-only data path.
# This never calls submit_order or any lifecycle method.
try:
    from ranker.alpaca_paper import AlpacaPaperClient
    observed = AlpacaPaperClient().stock_quote(symbol, allow_delayed=True)
    print(json.dumps({"test": "installed_primary_underlying_fallback", "result": "pass",
                      "symbol": symbol, "data": observed}, default=str), flush=True)
except Exception as exc:
    failures.append("installed_primary_underlying_fallback")
    print(json.dumps({"test": "installed_primary_underlying_fallback", "result": "fail",
                      "error": type(exc).__name__}), flush=True)

print(json.dumps({"summary": "pass" if not failures else "fail", "failures": failures,
                  "quote_age_seconds": age, "contract": contract}), flush=True)
raise SystemExit(bool(failures))
