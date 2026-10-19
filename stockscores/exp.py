"""
Simple backend-driven backtest runner for inspection.

This script boots the Django app and calls the existing backtester
(`stockscores.ranker.backtest.run_basket_backtest`) so you can
see what the backend is doing without touching the frontend.

Usage:
    python exp.py --symbols AAPL,MSFT --start 2023-01-01 --end 2024-01-01
Optional:
    --capital 10000          (starting equity)
    --rebalance-days 5       (only used if your strategy spec needs it)
    --top-n 5                (only used if your strategy spec needs it)
    --strategy strategy.json (path to a StrategySpec JSON file; defaults to a simple SMA crossover)
"""

import argparse
import json
import os
import sys
from pathlib import Path

import django


def bootstrap_django():
    # Ensure the Django project package is on PYTHONPATH
    project_root = Path(__file__).parent / "stockscores"
    sys.path.append(str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockscores.settings")
    django.setup()


def load_strategy(path: str | None):
    if not path:
        # Default strategy spec: simple SMA crossover
        return {
          "entry_tree": {
            "type": "condition",
            "indicator": "sma",
            "operator": "gt",
            "left": {"indicator": "sma_fast"},
            "right": {"indicator": "sma_slow"},
          },
          "exit_tree": {
            "type": "condition",
            "indicator": "sma",
            "operator": "lt",
            "left": {"indicator": "sma_fast"},
            "right": {"indicator": "sma_slow"},
          },
          "parameters": {
            "sma_fast": {"type": "int", "default": 20},
            "sma_slow": {"type": "int", "default": 50},
          },
          "metadata": {},
        }
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    parser = argparse.ArgumentParser(description="Backend backtest runner")
    parser.add_argument("--symbols", required=True, help="Comma-separated tickers, e.g. AAPL,MSFT")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=10_000.0, help="Starting equity")
    parser.add_argument("--rebalance-days", type=int, default=5, dest="rebalance_days")
    parser.add_argument("--top-n", type=int, default=None, dest="top_n")
    parser.add_argument("--strategy", type=str, default=None, help="Path to StrategySpec JSON")
    args = parser.parse_args()

    bootstrap_django()
    from stockscores.ranker.backtest import run_basket_backtest

    tickers = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    strategy_spec = load_strategy(args.strategy)

    print(f"Running backend backtest for {tickers} {args.start} -> {args.end}")
    result = run_basket_backtest(
        tickers=tickers,
        start=args.start,
        end=args.end,
        benchmark="SPY",
        initial_capital=args.capital,
        rebalance_days=args.rebalance_days,
        top_n=args.top_n,
        commission_per_trade=0.0,
        commission_pct=0.0,
        slippage_model="none",
        slippage_bps=0.0,
        max_open_positions=None,
        max_per_position_pct=1.0,
        strategy_spec=strategy_spec,
    )

    summary = result.summary or {}
    trades = result.trades or []

    print("\nSummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print(f"\nTrades ({len(trades)}):")
    for t in trades:
        print(
            f"  {t.get('symbol','?')} "
            f"{t.get('entry_time','?')} -> {t.get('exit_time','open')} "
            f"qty={t.get('qty','?')} entry={t.get('entry_price','?')} exit={t.get('exit_price','?')} "
            f"pnl={t.get('pnl','?')}"
        )


if __name__ == "__main__":
    main()
