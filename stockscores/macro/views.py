from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .data_fetchers import fetch_macro_dataset
from .narrative import build_narrative, build_playbook
from .options_engine import (
    build_trade_context,
    generate_option_suggestions,
    rank_option_suggestions,
)
from .regimes import compute_confidence_score, compute_regime_scores, determine_regime_label
from .signals import build_signal_table


class MacroDashboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        dataset = fetch_macro_dataset(min_history_days=126)
        signal_rows = build_signal_table(dataset)
        scores = compute_regime_scores(signal_rows)
        regime_label = determine_regime_label(scores)
        confidence = compute_confidence_score(scores)
        narrative = build_narrative(scores, regime_label)
        playbook = build_playbook(regime_label)

        trade_context = build_trade_context(
            regime=regime_label,
            confidence=confidence,
            risk_tolerance=request.query_params.get("risk_tolerance", "moderate"),
            position_context=request.query_params.get("position_context", "flat"),
            iv_context=request.query_params.get("iv_context", "normal"),
        )
        option_candidates = generate_option_suggestions(trade_context)
        option_suggestions = rank_option_suggestions(option_candidates, trade_context)

        as_of_candidates = []
        for item in dataset.values():
            series = item.get("series")
            if series is not None and not series.empty:
                as_of_candidates.append(series.index[-1])
        as_of = max(as_of_candidates).date().isoformat() if as_of_candidates else None

        return Response(
            {
                "as_of": as_of,
                "overall_regime": regime_label,
                "confidence": confidence,
                "scores": scores,
                "signals": [
                    {
                        "symbol": row["symbol"],
                        "name": row["name"],
                        "price": row["price"],
                        "ret_5d": row["ret_5d"],
                        "ret_20d": row["ret_20d"],
                        "ret_60d": row["ret_60d"],
                        "dist_50dma": row["dist_50dma"],
                        "signal": row["signal"],
                        "interpretation": row["interpretation"],
                    }
                    for row in signal_rows
                ],
                "narrative": narrative,
                "playbook": playbook,
                "options_engine": {
                    "trade_context": trade_context,
                    "suggestions": option_suggestions,
                },
            }
        )
