export const STRATEGY_TEMPLATES = [
  {
    id: "rsi_dip_buyer",
    name: "RSI Dip Buyer",
    description: "Buy dips when RSI is oversold; exit when RSI mean reverts.",
    spec: {
      entry_tree: {
        type: "condition",
        indicator: "rsi",
        operator: "lt",
        value_param: "rsi_entry_level",
        lookback: { param: "rsi_period" },
      },
      exit_tree: {
        type: "condition",
        indicator: "rsi",
        operator: "gt",
        value_param: "rsi_exit_level",
        lookback: { param: "rsi_period" },
      },
      parameters: {
        rsi_period: { type: "int", default: 14, min: 2, max: 100 },
        rsi_entry_level: { type: "float", default: 30, min: 5, max: 60 },
        rsi_exit_level: { type: "float", default: 55, min: 30, max: 95 },
      },
      metadata: {
        style: "mean_reversion",
        notes: "Classic RSI dip buying playbook.",
      },
    },
  },
  {
    id: "sma_crossover",
    name: "SMA Crossover",
    description: "Enter on a fast/slow SMA bull cross; exit on bear cross.",
    spec: {
      entry_tree: {
        type: "condition",
        indicator: "sma_fast",
        operator: "gt",
        value_param: "slow_sma_value",
        lookback: { param: "fast_length" },
      },
      exit_tree: {
        type: "condition",
        indicator: "sma_fast",
        operator: "lt",
        value_param: "slow_sma_value",
        lookback: { param: "fast_length" },
      },
      parameters: {
        fast_length: { type: "int", default: 20, min: 2, max: 200 },
        slow_length: { type: "int", default: 50, min: 5, max: 400 },
        slow_sma_value: {
          type: "float",
          default: 0,
          min: -1000,
          max: 1000,
          description: "Target slow SMA value; adjust with slow_length upstream.",
        },
      },
      metadata: {
        style: "trend_following",
        notes: "Simple two-line moving average crossover.",
      },
    },
  },
  {
    id: "breakout_high",
    name: "Breakout High",
    description: "Buy when price breaks above N-day high; trail a stop on new lows.",
    spec: {
      entry_tree: {
        type: "condition",
        indicator: "close",
        operator: "gt",
        value_param: "lookback_high_level",
        lookback: { param: "lookback_high" },
      },
      exit_tree: {
        type: "condition",
        indicator: "close",
        operator: "lt",
        value_param: "stop_level",
        lookback: { param: "stop_lookback" },
      },
      parameters: {
        lookback_high: { type: "int", default: 20, min: 5, max: 200 },
        lookback_high_level: {
          type: "float",
          default: 0,
          min: -1000,
          max: 100000,
          description: "N-day breakout threshold (set by upstream calculator).",
        },
        stop_lookback: { type: "int", default: 10, min: 2, max: 100 },
        stop_level: {
          type: "float",
          default: 0,
          min: -1000,
          max: 100000,
          description: "Trailing stop threshold (set by upstream calculator).",
        },
      },
      metadata: {
        style: "breakout",
        notes: "Donchian-style breakout with trailing exit.",
      },
    },
  },
];
