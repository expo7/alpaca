"""Data fetchers for Macro Dashboard v1.

Uses Yahoo Finance as the initial data source with sensible symbol fallbacks
for instruments that can be inconsistent across regions/accounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class TrackedAsset:
    key: str
    name: str
    candidates: List[str]


TRACKED_ASSETS: List[TrackedAsset] = [
    TrackedAsset("UST10Y", "US 10Y Yield", ["^TNX", "IEF"]),
    TrackedAsset("UST3M", "US 3M T-Bill", ["^IRX", "SHY"]),
    TrackedAsset("DXY", "US Dollar Index", ["DX-Y.NYB", "UUP"]),
    TrackedAsset("USDJPY", "USD/JPY", ["JPY=X"]),
    TrackedAsset("EURUSD", "EUR/USD", ["EURUSD=X"]),
    TrackedAsset("CRUDE", "WTI Crude", ["CL=F"]),
    TrackedAsset("GOLD", "Gold", ["GC=F"]),
    TrackedAsset("COPPER", "Copper", ["HG=F"]),
    TrackedAsset("SPY", "SPDR S&P 500 ETF", ["SPY"]),
    TrackedAsset("QQQ", "Invesco QQQ", ["QQQ"]),
    TrackedAsset("IWM", "iShares Russell 2000 ETF", ["IWM"]),
    TrackedAsset("EEM", "iShares MSCI Emerging Markets ETF", ["EEM"]),
    TrackedAsset("HYG", "iShares iBoxx High Yield Corp Bond ETF", ["HYG"]),
    TrackedAsset("LQD", "iShares iBoxx Investment Grade Corp Bond ETF", ["LQD"]),
]


def _extract_close_series(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)

    for col in ("Adj Close", "Close"):
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if not series.empty:
                return series

    return pd.Series(dtype=float)


def _download_series(symbol: str, period: str = "9mo", interval: str = "1d") -> pd.Series:
    # Keep v1 intentionally simple and explicit: one ticker per call improves
    # debuggability when proxies fail.
    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    series = _extract_close_series(df)
    if series.empty:
        return series
    series.index = pd.to_datetime(series.index).tz_localize(None)
    return series.sort_index()


def fetch_macro_dataset(min_history_days: int = 126) -> Dict[str, dict]:
    """Fetch tracked assets with fallbacks and return normalized payloads.

    `min_history_days=126` approximates six months of trading days.
    """
    payload: Dict[str, dict] = {}

    for asset in TRACKED_ASSETS:
        selected_symbol: Optional[str] = None
        selected_series = pd.Series(dtype=float)

        for candidate in asset.candidates:
            series = _download_series(candidate)
            if len(series) >= min_history_days:
                selected_symbol = candidate
                selected_series = series
                break
            if selected_series.empty and not series.empty:
                # Keep first non-empty candidate as a fallback even if short.
                selected_symbol = candidate
                selected_series = series

        payload[asset.key] = {
            "key": asset.key,
            "name": asset.name,
            "symbol": selected_symbol,
            "series": selected_series,
            "fallback_candidates": asset.candidates,
        }

    return payload
