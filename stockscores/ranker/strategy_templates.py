from copy import deepcopy
from typing import Dict, List, Optional

from .serializers import StrategySpecSerializer


BUILT_IN_TEMPLATES: List[Dict[str, object]] = [
    {
        "id": "rsi_dip_buyer",
        "name": "RSI Dip Buyer",
        "description": "Buys when RSI is oversold and exits as momentum normalizes.",
        "strategy_spec": {
            "name": "RSI Dip Buyer",
            "entry_tree": {
                "type": "condition",
                "indicator": "rsi",
                "operator": "lt",
                "value": {"param": "rsi_entry_level"},
                "lookback": {"param": "rsi_period"},
            },
            "exit_tree": {
                "type": "condition",
                "indicator": "rsi",
                "operator": "gt",
                "value": {"param": "rsi_exit_level"},
                "lookback": {"param": "rsi_period"},
            },
            "parameters": {
                "rsi_period": {"type": "int", "default": 14, "min": 2, "max": 50},
                "rsi_entry_level": {
                    "type": "float",
                    "default": 30,
                    "min": 5,
                    "max": 50,
                },
                "rsi_exit_level": {
                    "type": "float",
                    "default": 60,
                    "min": 40,
                    "max": 90,
                },
            },
            "metadata": {
                "style": "mean_reversion",
                "notes": "Look for oversold dips on liquid names.",
            },
        },
    },
    {
        "id": "macd_trend_follower",
        "name": "MACD Trend Follower",
        "description": "Rides medium-term trends with a MACD signal filter.",
        "strategy_spec": {
            "name": "MACD Trend Follower",
            "entry_tree": {
                "type": "and",
                "children": [
                    {
                        "type": "condition",
                        "indicator": "macd_signal",
                        "operator": "gt",
                        "value": {"param": "macd_signal_min"},
                    },
                    {
                        "type": "condition",
                        "indicator": "ema_trend",
                        "operator": "gt",
                        "value": {"param": "trend_filter"},
                        "lookback": {"param": "ema_period"},
                    },
                ],
            },
            "exit_tree": {
                "type": "condition",
                "indicator": "macd_signal",
                "operator": "lt",
                "value": {"param": "macd_exit_threshold"},
            },
            "parameters": {
                "macd_signal_min": {
                    "type": "float",
                    "default": 0.0,
                    "min": -2.0,
                    "max": 5.0,
                },
                "macd_exit_threshold": {
                    "type": "float",
                    "default": -0.5,
                    "min": -5.0,
                    "max": 2.0,
                },
                "trend_filter": {
                    "type": "float",
                    "default": 0.0,
                    "min": -0.05,
                    "max": 0.2,
                },
                "ema_period": {"type": "int", "default": 21, "min": 5, "max": 55},
            },
            "metadata": {"style": "trend", "notes": "Stay with the trend until MACD rolls over."},
        },
    },
    {
        "id": "golden_cross_swing",
        "name": "Golden Cross Swing",
        "description": "Classic fast/slow moving-average cross with a small buffer.",
        "strategy_spec": {
            "name": "Golden Cross Swing",
            "entry_tree": {
                "type": "condition",
                "indicator": "sma_cross",
                "operator": "gt",
                "value": {"param": "cross_buffer"},
                "left": {"param": "fast_length"},
                "right": {"param": "slow_length"},
            },
            "exit_tree": {
                "type": "condition",
                "indicator": "sma_cross",
                "operator": "lt",
                "value": {"param": "exit_buffer"},
                "left": {"param": "fast_length"},
                "right": {"param": "slow_length"},
            },
            "parameters": {
                "fast_length": {"type": "int", "default": 20, "min": 5, "max": 60},
                "slow_length": {"type": "int", "default": 50, "min": 20, "max": 200},
                "cross_buffer": {"type": "float", "default": 0.0, "min": -0.05, "max": 0.1},
                "exit_buffer": {"type": "float", "default": -0.01, "min": -0.1, "max": 0.05},
            },
            "metadata": {
                "style": "trend",
                "notes": "Fast SMA crossing above slow SMA with buffer before entry.",
            },
        },
    },
    {
        "id": "volume_spike_breakout",
        "name": "Volume Spike Breakout",
        "description": "Looks for fresh breakouts backed by expanding volume.",
        "strategy_spec": {
            "name": "Volume Spike Breakout",
            "entry_tree": {
                "type": "and",
                "children": [
                    {
                        "type": "condition",
                        "indicator": "volume_spike",
                        "operator": "gt",
                        "value": {"param": "volume_multiplier"},
                    },
                    {
                        "type": "condition",
                        "indicator": "price_breakout",
                        "operator": "gt",
                        "value": {"param": "breakout_pct"},
                        "lookback": {"param": "breakout_lookback"},
                    },
                ],
            },
            "exit_tree": {
                "type": "condition",
                "indicator": "trailing_stop",
                "operator": "lt",
                "value": {"param": "trailing_stop_pct"},
            },
            "parameters": {
                "volume_multiplier": {
                    "type": "float",
                    "default": 1.5,
                    "min": 1.0,
                    "max": 5.0,
                },
                "breakout_pct": {
                    "type": "float",
                    "default": 0.03,
                    "min": 0.0,
                    "max": 0.2,
                },
                "breakout_lookback": {"type": "int", "default": 20, "min": 5, "max": 120},
                "trailing_stop_pct": {
                    "type": "float",
                    "default": -0.05,
                    "min": -0.3,
                    "max": -0.01,
                },
            },
            "metadata": {"style": "momentum", "notes": "Momentum/volume confirmation breakout."},
        },
    },
]


def _validate_template(raw_template: Dict[str, object]) -> Dict[str, object]:
    serializer = StrategySpecSerializer(data=raw_template["strategy_spec"])
    serializer.is_valid(raise_exception=True)
    return {
        "id": raw_template["id"],
        "name": raw_template["name"],
        "description": raw_template.get("description", ""),
        "strategy_spec": serializer.validated_data,
    }


_VALIDATED_TEMPLATES: List[Dict[str, object]] = [
    _validate_template(tpl) for tpl in BUILT_IN_TEMPLATES
]


def list_templates() -> List[Dict[str, object]]:
    return [deepcopy(tpl) for tpl in _VALIDATED_TEMPLATES]


def get_template(template_id: str) -> Optional[Dict[str, object]]:
    for tpl in _VALIDATED_TEMPLATES:
        if tpl["id"] == template_id:
            return deepcopy(tpl)
    return None
