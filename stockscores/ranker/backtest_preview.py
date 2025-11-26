from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class PreviewSignal:
    symbol: str
    action: str  # buy | sell | hold
    confidence: float
    indicators: Dict[str, float]


def _sma(series: pd.Series, window: int) -> Optional[Decimal]:
    if series is None or series.empty or len(series) < window:
        return None
    return Decimal(str(series.tail(window).mean()))


def _rsi(series: pd.Series, window: int) -> Optional[Decimal]:
    if series is None or series.empty or len(series) < window:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = -delta.clip(upper=0).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return Decimal(str(rsi.iloc[-1])) if not rsi.empty else None


def _indicator_snapshot(close_series: pd.Series, params: dict) -> Dict[str, float]:
    snap = {}
    fast = params.get("fast_length")
    slow = params.get("slow_length")
    rsi_window = params.get("rsi_period") or params.get("rsi_window")
    if fast:
        val = _sma(close_series, int(fast))
        if val is not None:
            snap["sma_fast"] = float(val)
    if slow:
        val = _sma(close_series, int(slow))
        if val is not None:
            snap["sma_slow"] = float(val)
    if rsi_window:
        val = _rsi(close_series, int(rsi_window))
        if val is not None:
            snap["rsi"] = float(val)
    return snap


def preview_strategy_signals(
    strategy_spec: Dict[str, Any],
    bot_config: Dict[str, Any],
    bars: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Lightweight preview: evaluate indicators on recent bars and propose actions.
    """
    if bars is None or bars.empty:
        return {
            "signals": [],
            "equity_estimate": 0.0,
            "pnl_since_forward": 0.0,
            "would_trade": False,
            "recommended_orders": [],
        }

    symbols = bot_config.get("symbols") or []
    if isinstance(symbols, str):
        symbols = [symbols]
    signals: List[PreviewSignal] = []

    # Use close series; assume bars is wide with columns like Close_<SYM> or multi-index.
    # Fallback to single symbol dataframe.
    close_cols = [c for c in bars.columns if c.lower().startswith("close")]
    if not close_cols and "Close" in bars.columns:
        close_cols = ["Close"]

    for sym in symbols:
        col = f"Close_{sym}"
        if col not in bars.columns:
            col = "Close"
        if col not in bars.columns:
            continue
        close_series = bars[col].dropna()
        params = strategy_spec.get("parameters") or {}
        snap = _indicator_snapshot(close_series, params)
        action = "hold"
        confidence = 0.0

        # Heuristic: look for basic mean-reversion or trend cues based on available params
        rsi_val = snap.get("rsi")
        rsi_entry = params.get("rsi_entry_level")
        rsi_exit = params.get("rsi_exit_level")
        fast = snap.get("sma_fast")
        slow = snap.get("sma_slow")
        if rsi_val is not None and rsi_entry is not None and rsi_val <= float(rsi_entry):
            action = "buy"
            confidence = 0.7
        if rsi_val is not None and rsi_exit is not None and rsi_val >= float(rsi_exit):
            action = "sell"
            confidence = 0.7
        if fast is not None and slow is not None:
            if fast > slow:
                action = "buy"
                confidence = max(confidence, 0.6)
            elif fast < slow:
                action = "sell"
                confidence = max(confidence, 0.6)

        signals.append(
            PreviewSignal(
                symbol=sym,
                action=action,
                confidence=confidence,
                indicators=snap,
            )
        )

    would_trade = any(sig.action in {"buy", "sell"} for sig in signals)
    recommended_orders = []
    qty_hint = bot_config.get("quantity") or bot_config.get("notional")
    for sig in signals:
        if sig.action == "hold":
            continue
        recommended_orders.append(
            {
                "symbol": sig.symbol,
                "side": "buy" if sig.action == "buy" else "sell",
                "qty": qty_hint or 0,
                "type": "market",
            }
        )

    return {
        "signals": [
            {
                "symbol": sig.symbol,
                "action": sig.action,
                "confidence": sig.confidence,
                "indicators": sig.indicators,
            }
            for sig in signals
        ],
        "equity_estimate": float(bot_config.get("capital") or 0.0),
        "pnl_since_forward": 0.0,
        "would_trade": would_trade,
        "recommended_orders": recommended_orders,
    }
