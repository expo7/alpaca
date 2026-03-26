"""Narrative and playbook generation for Macro Dashboard MVP."""

from __future__ import annotations

from typing import Dict, List


def build_narrative(scores: Dict[str, float], regime_label: str) -> str:
    growth = scores.get("growth", 0.0)
    inflation = scores.get("inflation", 0.0)
    liquidity = scores.get("liquidity", 0.0)
    risk = scores.get("risk_appetite", 0.0)

    growth_txt = "accelerating" if growth >= 10 else "soft" if growth <= -10 else "mixed"
    inflation_txt = "firm" if inflation >= 10 else "cooling" if inflation <= -10 else "stable"
    liquidity_txt = "supportive" if liquidity >= 10 else "tight" if liquidity <= -10 else "neutral"
    risk_txt = "constructive" if risk >= 10 else "defensive" if risk <= -10 else "balanced"

    return (
        f"Current regime reads as {regime_label}. Growth signals are {growth_txt}, "
        f"inflation pressure is {inflation_txt}, liquidity is {liquidity_txt}, "
        f"and cross-asset risk tone is {risk_txt}."
    )


def build_playbook(regime_label: str) -> Dict[str, List[str] | str]:
    if regime_label == "Risk-On Expansion":
        return {
            "favored_assets": ["SPY", "QQQ", "IWM", "EEM", "HYG"],
            "unfavorable_assets": ["DXY", "LQD"],
            "notes": "Prefer cyclical equity and high-beta exposures while keeping rate/FX volatility in view.",
        }

    if regime_label == "Inflationary Expansion":
        return {
            "favored_assets": ["CL=F", "GC=F", "HG=F", "Value/Cyclicals"],
            "unfavorable_assets": ["Long-duration bonds", "Rate-sensitive growth"],
            "notes": "Bias toward real assets and inflation beneficiaries; avoid duration-heavy risk.",
        }

    if regime_label == "Tightening Risk-Off":
        return {
            "favored_assets": ["DXY", "Cash", "Short duration"],
            "unfavorable_assets": ["IWM", "EEM", "HYG", "High-beta tech"],
            "notes": "Prioritize balance-sheet quality, reduce leverage, and tighten risk limits.",
        }

    if regime_label == "Disinflation / Defensive":
        return {
            "favored_assets": ["LQD", "Quality large caps", "Defensive sectors"],
            "unfavorable_assets": ["Cyclicals", "Energy beta"],
            "notes": "Lean defensive while waiting for stronger growth confirmation.",
        }

    return {
        "favored_assets": ["Balanced allocation", "Quality factors"],
        "unfavorable_assets": ["Highly concentrated directional bets"],
        "notes": "Signals are mixed; position sizing and diversification matter more than aggressive factor bets.",
    }
