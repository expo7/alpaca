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
    TrackedAsset("GOLD", "Gold", ["GLD", "GC=F"]),
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

    for target in ("Adj Close", "Close"):
        for col in _candidate_columns(df, target):
            series = _to_numeric_series(df[col]).dropna()
            if not series.empty:
                return series

    # Final fallback for unusual provider payloads with a single column.
    if len(df.columns) == 1:
        series = _to_numeric_series(df.iloc[:, 0]).dropna()
        if not series.empty:
            return series

    return pd.Series(dtype=float)


def _candidate_columns(df: pd.DataFrame, target: str) -> List[object]:
    """Return concrete column labels matching target across flat/MultiIndex schemas."""
    cols: List[object] = []
    if isinstance(df.columns, pd.MultiIndex):
        for col in df.columns:
            if isinstance(col, tuple) and col and col[0] == target:
                cols.append(col)
    else:
        if target in df.columns:
            cols.append(target)
    return cols


def _to_numeric_series(value: object) -> pd.Series:
    """Safely coerce a 1-D numeric Series without allowing 2-D objects."""
    if isinstance(value, pd.Series):
        return pd.to_numeric(value, errors="coerce")

    # yfinance can produce 2-D frames for grouped columns; consume column-by-column.
    if isinstance(value, pd.DataFrame):
        for col in value.columns:
            series = pd.to_numeric(value[col], errors="coerce")
            if isinstance(series, pd.Series) and not series.dropna().empty:
                return series
        return pd.Series(dtype=float)

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
