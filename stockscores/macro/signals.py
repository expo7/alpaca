"""Signal and per-symbol metric calculations for Macro Dashboard."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


def _pct_return(series: pd.Series, days: int) -> Optional[float]:
    if series is None or len(series) <= days:
        return None
    base = float(series.iloc[-days - 1])
    latest = float(series.iloc[-1])
    if base == 0:
        return None
    return ((latest / base) - 1.0) * 100.0


def _dist_50dma(series: pd.Series) -> Optional[float]:
    if series is None or len(series) < 50:
        return None
    ma50 = series.rolling(50).mean().iloc[-1]
    latest = float(series.iloc[-1])
    if pd.isna(ma50) or ma50 == 0:
        return None
    return ((latest / float(ma50)) - 1.0) * 100.0


def _round(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(float(v), 2)


def classify_signal(ret_20d: Optional[float], dist_50dma: Optional[float]) -> tuple[str, str]:
    if ret_20d is None or dist_50dma is None:
        return "Unavailable", "Insufficient recent data for this symbol."

    if ret_20d > 2 and dist_50dma > 0:
        return "Bullish", "Momentum is positive and price sits above its 50DMA."
    if ret_20d < -2 and dist_50dma < 0:
        return "Bearish", "Momentum is negative and price is below its 50DMA."
    return "Neutral", "Mixed short-term trend; no strong directional bias."


def build_signal_table(dataset: Dict[str, dict]) -> List[dict]:
    signals: List[dict] = []

    for _, asset in dataset.items():
        series = asset.get("series")
        symbol = asset.get("symbol")
        price = float(series.iloc[-1]) if series is not None and not series.empty else None

        ret_5d = _pct_return(series, 5)
        ret_20d = _pct_return(series, 20)
        ret_60d = _pct_return(series, 60)
        dist_50dma = _dist_50dma(series)

        signal, interpretation = classify_signal(ret_20d, dist_50dma)

        signals.append(
            {
                "key": asset.get("key"),
                "symbol": symbol or "N/A",
                "name": asset.get("name"),
                "price": _round(price),
                "ret_5d": _round(ret_5d),
                "ret_20d": _round(ret_20d),
                "ret_60d": _round(ret_60d),
                "dist_50dma": _round(dist_50dma),
                "signal": signal,
                "interpretation": interpretation,
            }
        )

    return signals
