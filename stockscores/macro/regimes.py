"""Interpretable regime scoring logic for Macro Dashboard MVP."""

from __future__ import annotations

from typing import Dict, List, Optional


def _clamp(value: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _avg(values: List[Optional[float]]) -> float:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return 0.0
    return sum(clean) / len(clean)


def _metric(signals: Dict[str, dict], key: str, field: str) -> Optional[float]:
    item = signals.get(key) or {}
    value = item.get(field)
    return float(value) if value is not None else None


def compute_regime_scores(signal_table: List[dict]) -> Dict[str, float]:
    """Compute bounded regime scores from normalized cross-asset signals.

    Inputs are intentionally simple price-derived metrics for interpretability.
    """
    by_key: Dict[str, dict] = {
        str(row["key"]): row for row in signal_table if row.get("key") is not None
    }

    growth_raw = _avg(
        [
            _metric(by_key, "SPY", "ret_20d"),
            _metric(by_key, "QQQ", "ret_20d"),
            _metric(by_key, "IWM", "ret_20d"),
            _metric(by_key, "EEM", "ret_20d"),
            _metric(by_key, "COPPER", "ret_20d"),
            _metric(by_key, "SPY", "dist_50dma"),
        ]
    )

    inflation_raw = _avg(
        [
            _metric(by_key, "CRUDE", "ret_20d"),
            _metric(by_key, "GOLD", "ret_20d"),
            _metric(by_key, "COPPER", "ret_20d"),
            _metric(by_key, "UST10Y", "ret_20d"),
        ]
    )

    liquidity_raw = _avg(
        [
            -1.0 * (_metric(by_key, "DXY", "ret_20d") or 0.0),
            -1.0 * (_metric(by_key, "UST3M", "ret_20d") or 0.0),
            _metric(by_key, "LQD", "ret_20d"),
            _metric(by_key, "HYG", "ret_20d"),
        ]
    )

    risk_raw = _avg(
        [
            _metric(by_key, "SPY", "ret_20d"),
            _metric(by_key, "QQQ", "ret_20d"),
            _metric(by_key, "IWM", "ret_20d"),
            _metric(by_key, "EEM", "ret_20d"),
            _metric(by_key, "HYG", "ret_20d"),
            _metric(by_key, "LQD", "ret_20d"),
            _metric(by_key, "USDJPY", "ret_20d"),
        ]
    )

    scores = {
        "growth": round(_clamp(growth_raw * 6.0), 1),
        "inflation": round(_clamp(inflation_raw * 8.0), 1),
        "liquidity": round(_clamp(liquidity_raw * 10.0), 1),
        "risk_appetite": round(_clamp(risk_raw * 8.0), 1),
    }

    return scores


def determine_regime_label(scores: Dict[str, float]) -> str:
    """Map score combinations to one explicit human-readable regime label."""
    growth = scores.get("growth", 0.0)
    inflation = scores.get("inflation", 0.0)
    liquidity = scores.get("liquidity", 0.0)
    risk = scores.get("risk_appetite", 0.0)

    if liquidity <= -15 and risk <= -10:
        return "Tightening Risk-Off"
    if risk >= 20 and growth >= 20 and inflation < 25 and liquidity >= 0:
        return "Risk-On Expansion"
    if growth >= 10 and inflation >= 20 and risk >= 0:
        return "Inflationary Expansion"
    if inflation <= -10 and (risk <= 5 or growth <= 0):
        return "Disinflation / Defensive"
    return "Mixed / Transition"


def compute_confidence_score(scores: Dict[str, float]) -> int:
    values = [
        scores.get("growth", 0.0),
        scores.get("inflation", 0.0),
        scores.get("liquidity", 0.0),
        scores.get("risk_appetite", 0.0),
    ]

    active = [v for v in values if abs(v) >= 10]
    if not active:
        return 35

    positives = sum(1 for v in active if v > 0)
    negatives = sum(1 for v in active if v < 0)
    agreement = max(positives, negatives) / len(active)
    magnitude = sum(abs(v) for v in active) / (len(active) * 100.0)

    score = 35 + (agreement * 35) + (magnitude * 25)
    return int(round(_clamp(score, 35, 95)))
