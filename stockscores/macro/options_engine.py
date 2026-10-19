"""Deterministic rule-based options suggestion layer for Macro Dashboard."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List


ALLOWED_RISK = {"conservative", "moderate", "aggressive"}
ALLOWED_POSITION = {"flat", "long_shares"}
ALLOWED_IV = {"low", "normal", "high"}


STRATEGY_LIBRARY: Dict[str, dict] = {
    "covered_call": {
        "strategy": "covered_call",
        "label": "Covered Call Overlay",
        "reason": "Monetize existing long shares while moderating upside participation.",
        "setup": {"dte": "30-45", "delta_target": "0.20-0.30", "bias": "neutral_to_slightly_bullish"},
        "fits_when": ["long_shares", "iv_context_high", "sideways_to_moderate_upside"],
        "avoid_when": ["expecting_large_upside_breakout", "no_existing_share_position"],
        "base_priority": 62,
        "iv_preference": "high",
        "position_preference": "long_shares",
        "risk_fit": {"conservative", "moderate"},
    },
    "call_credit_spread": {
        "strategy": "call_credit_spread",
        "label": "Bearish Call Credit Spread",
        "reason": "Define risk while expressing a bearish-to-neutral view in weaker tapes.",
        "setup": {"dte": "21-45", "delta_target": "0.20-0.30 short call", "bias": "bearish"},
        "fits_when": ["risk_off", "range_to_downtrend", "iv_context_high_or_normal"],
        "avoid_when": ["strong_uptrend", "low_liquidity_underlyings"],
        "base_priority": 64,
        "iv_preference": "high",
        "position_preference": "any",
        "risk_fit": {"moderate", "aggressive"},
    },
    "put_spread": {
        "strategy": "put_spread",
        "label": "Bear Put Spread",
        "reason": "Capture downside regime risk with defined premium outlay.",
        "setup": {"dte": "30-60", "delta_target": "0.30-0.40 long put", "bias": "bearish"},
        "fits_when": ["risk_off", "downtrend_confirmation", "event_risk_elevated"],
        "avoid_when": ["choppy_mean_reverting_market", "rapid_iv_crush"],
        "base_priority": 66,
        "iv_preference": "normal",
        "position_preference": "any",
        "risk_fit": {"moderate", "aggressive"},
    },
    "cash_secured_put": {
        "strategy": "cash_secured_put",
        "label": "Cash-Secured Put",
        "reason": "Seek premium while potentially entering long exposure at lower effective basis.",
        "setup": {"dte": "30-45", "delta_target": "0.20-0.30 short put", "bias": "bullish_to_neutral"},
        "fits_when": ["risk_on_or_stable", "flat_position", "willing_to_own_underlying"],
        "avoid_when": ["sharp_bear_regime", "insufficient_cash_collateral"],
        "base_priority": 61,
        "iv_preference": "high",
        "position_preference": "flat",
        "risk_fit": {"conservative", "moderate"},
    },
    "call_spread": {
        "strategy": "call_spread",
        "label": "Bull Call Spread",
        "reason": "Express upside bias with capped cost and bounded risk.",
        "setup": {"dte": "30-60", "delta_target": "0.30-0.40 long call", "bias": "bullish"},
        "fits_when": ["risk_on", "uptrend", "defined_risk_preference"],
        "avoid_when": ["strong_bear_trend", "very_high_iv_without_edge"],
        "base_priority": 65,
        "iv_preference": "low",
        "position_preference": "any",
        "risk_fit": {"moderate", "aggressive"},
    },
    "long_duration_call_spread": {
        "strategy": "long_duration_call_spread",
        "label": "Long-Duration Call Spread",
        "reason": "Use longer horizon upside structure when trend quality is improving but still selective.",
        "setup": {"dte": "90-180", "delta_target": "0.35-0.45 long call", "bias": "bullish_defensive"},
        "fits_when": ["disinflation_defensive", "gradual_recovery", "time_diversification"],
        "avoid_when": ["near_term_high_conviction_bearish", "very_high_iv_term_structure"],
        "base_priority": 60,
        "iv_preference": "low",
        "position_preference": "any",
        "risk_fit": {"conservative", "moderate"},
    },
}


def _normalize(value: str, allowed: set[str], default: str) -> str:
    if not isinstance(value, str):
        return default
    clean = value.strip().lower()
    return clean if clean in allowed else default


def build_trade_context(
    regime: str,
    confidence: int,
    risk_tolerance: str,
    position_context: str,
    iv_context: str,
) -> dict:
    """Build normalized user+regime context used for deterministic strategy rules."""
    return {
        "regime": regime or "Mixed / Transition",
        "confidence": int(confidence or 0),
        "risk_tolerance": _normalize(risk_tolerance, ALLOWED_RISK, "moderate"),
        "position_context": _normalize(position_context, ALLOWED_POSITION, "flat"),
        "iv_context": _normalize(iv_context, ALLOWED_IV, "normal"),
    }


def _pick(strategy_key: str, reason: str | None = None) -> dict:
    item = deepcopy(STRATEGY_LIBRARY[strategy_key])
    if reason:
        item["reason"] = reason
    return item


def generate_option_suggestions(trade_context: dict) -> List[dict]:
    """Generate 1-3 regime-driven strategy candidates before scoring adjustments."""
    regime = trade_context.get("regime", "Mixed / Transition")
    position_context = trade_context.get("position_context", "flat")
    suggestions: List[dict] = []

    if regime == "Tightening Risk-Off":
        suggestions.extend(
            [
                _pick("put_spread"),
                _pick("call_credit_spread"),
            ]
        )
        if position_context == "long_shares":
            suggestions.append(
                _pick("covered_call", "In risk-off conditions, covered calls can reduce carry cost on existing longs.")
            )

    elif regime == "Risk-On Expansion":
        suggestions.extend(
            [
                _pick("call_spread"),
                _pick("cash_secured_put"),
                _pick("long_duration_call_spread"),
            ]
        )

    elif regime == "Inflationary Expansion":
        suggestions.extend(
            [
                _pick("call_spread", "Prefer upside structures in cyclical or commodity-linked exposures."),
                _pick("cash_secured_put"),
            ]
        )
        if position_context == "long_shares":
            suggestions.append(_pick("covered_call"))

    elif regime == "Disinflation / Defensive":
        suggestions.extend(
            [
                _pick("long_duration_call_spread"),
                _pick("call_spread", "Use selective upside spreads on defensive or quality leaders."),
            ]
        )
        if position_context == "long_shares":
            suggestions.append(_pick("covered_call"))

    else:
        suggestions.extend(
            [
                _pick("call_spread"),
                _pick("cash_secured_put"),
            ]
        )

    deduped: Dict[str, dict] = {}
    for row in suggestions:
        deduped[row["strategy"]] = row
    return list(deduped.values())[:3]


def rank_option_suggestions(suggestions: List[dict], trade_context: dict) -> List[dict]:
    """Apply simple deterministic ranking boosts/penalties from user context."""
    iv_context = trade_context.get("iv_context", "normal")
    position_context = trade_context.get("position_context", "flat")
    risk_tolerance = trade_context.get("risk_tolerance", "moderate")
    confidence = int(trade_context.get("confidence") or 0)

    ranked: List[dict] = []

    for row in suggestions:
        score = float(row.get("base_priority", 50))
        iv_pref = row.get("iv_preference", "normal")
        pos_pref = row.get("position_preference", "any")
        risk_fit = row.get("risk_fit", set())

        if iv_pref == iv_context:
            score += 8
        elif iv_pref != "normal" and iv_context != "normal":
            score -= 4

        if pos_pref == "any":
            score += 2
        elif pos_pref == position_context:
            score += 10
        else:
            score -= 20

        if isinstance(risk_fit, set) and risk_tolerance in risk_fit:
            score += 6
        else:
            score -= 4

        if confidence >= 65:
            score += 4

        if row.get("strategy") == "covered_call" and position_context != "long_shares":
            score -= 25
        if row.get("strategy") == "cash_secured_put" and position_context == "long_shares":
            score -= 6

        out = {
            "strategy": row["strategy"],
            "label": row["label"],
            "priority": int(round(score)),
            "reason": row["reason"],
            "setup": row["setup"],
            "fits_when": row["fits_when"],
            "avoid_when": row["avoid_when"],
        }
        ranked.append(out)

    ranked.sort(key=lambda item: item.get("priority", 0), reverse=True)
    return ranked[:3]
