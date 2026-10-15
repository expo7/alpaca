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
stocks = probe("stock_snapshots", data_url + "/v2/stocks/snapshots",
               {"symbols": "SPY,QQQ,IWM", "feed": "iex"})
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
print(json.dumps({"summary": "pass" if not failures else "fail", "failures": failures,
                  "quote_age_seconds": age, "contract": contract}), flush=True)
raise SystemExit(bool(failures))
