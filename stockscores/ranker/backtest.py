# ranker/backtest.py

import logging
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from .metrics import increment_yf_counter

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    tickers: List[str]
    start: str
    end: str
    equity_curve: List[Dict[str, Any]]
    benchmark_symbol: str
    benchmark_curve: List[Dict[str, Any]]
    summary: Dict[str, float]
    per_ticker: Optional[List[Dict[str, Any]]] = None


def _normalize_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize each column to start at 1.0 (price / first_valid_price).
    """
    norm = pd.DataFrame(index=df.index)
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue
        first = series.iloc[0]
        if first == 0 or np.isnan(first):
            continue
        norm[col] = df[col] / first
    return norm


def _max_drawdown(series: pd.Series) -> float:
    """
    Max drawdown as a fraction (e.g. -0.25 = -25%).
    """
    if series.empty:
        return 0.0
    roll_max = series.cummax()
    dd = (series - roll_max) / roll_max
    return float(dd.min()) if not dd.empty else 0.0


def _max_drawdown_duration(series: pd.Series) -> int:
    """
    Longest duration (in bars) spent below a prior peak.
    """
    peak = series.iloc[0] if not series.empty else 0.0
    duration = 0
    max_duration = 0
    for value in series:
        if value >= peak:
            peak = value
            duration = 0
        else:
            duration += 1
            max_duration = max(max_duration, duration)
    return int(max_duration)


def _contains_event_condition(node: Any) -> bool:
    if isinstance(node, dict):
        if node.get("type") == "event_condition":
            return True
        return any(_contains_event_condition(v) for v in node.values())
    if isinstance(node, list):
        return any(_contains_event_condition(v) for v in node)
    return False


def run_basket_backtest(
    tickers: List[str],
    start: str,
    end: str,
    benchmark: str = "SPY",
    initial_capital: float = 10_000.0,
    rebalance_days: int = 5,
    top_n: Optional[int] = None,
    commission_per_trade: float = 0.0,
    commission_pct: float = 0.0,
    slippage_model: str = "none",
    slippage_bps: float = 0.0,
    max_open_positions: Optional[int] = None,
    max_per_position_pct: float = 1.0,
    strategy_spec: Optional[Dict[str, Any]] = None,
) -> BacktestResult:
    """
    Top-N momentum basket backtest vs benchmark.

    Strategy:
      - Universe = provided tickers
      - Every `rebalance_days` trading days:
          * Compute simple momentum over a lookback window
            (price[today] / price[lookback_day] - 1)
          * Pick Top N tickers by momentum (N = top_n, capped by universe size)
          * Rebalance to equal-weight among those tickers
      - Between rebalances, hold that basket.

    Notes:
      - Transaction costs (commission + slippage) are applied on each rebalance.
      - Uses yfinance daily close prices
    """

    if strategy_spec and _contains_event_condition(
        strategy_spec.get("entry_tree")
    ):
        logger.warning("event_condition found in entry_tree but events are not wired yet; treating as False.")
    if strategy_spec and _contains_event_condition(strategy_spec.get("exit_tree")):
        logger.warning("event_condition found in exit_tree but events are not wired yet; treating as False.")

    # --- Clean & dedupe tickers ---
    tickers = sorted({t.upper() for t in tickers if t})
    if not tickers:
        raise ValueError("No valid tickers provided")

    if top_n is None or top_n <= 0:
        top_n = len(tickers)
    top_n = min(top_n, len(tickers))
    if max_open_positions is not None:
        top_n = min(top_n, max_open_positions)

    # -------------------------
    # 1) Download basket prices
    # -------------------------
    increment_yf_counter()
    data = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
    )

    if data.empty:
        raise ValueError("No price data returned for given inputs")

    if isinstance(data.columns, pd.MultiIndex):
        price = data["Close"]
    else:
        price = data[["Close"]]
        price.columns = tickers

    price = price.dropna(how="all")
    if price.empty:
        raise ValueError("No usable close prices for given tickers")

    price = price.ffill()

    # Daily returns for the strategy
    daily_ret = price.pct_change().fillna(0.0)

    # Normalized prices (for per-ticker stats later)
    norm = _normalize_price_df(price)

    dates = price.index
    n_days = len(dates)

    # -------------------------
    # 2) Build rebalance schedule
    # -------------------------
    rebal_indices = list(range(0, n_days, max(1, int(rebalance_days))))
    if rebal_indices[-1] != n_days - 1:
        rebal_indices.append(n_days - 1)

    equity_series = pd.Series(index=dates, dtype=float)
    equity = float(initial_capital)
    current_weights = pd.Series(0.0, index=price.columns)
    trades: List[Dict[str, Any]] = []

    for k in range(len(rebal_indices) - 1):
        start_idx = rebal_indices[k]
        end_idx = rebal_indices[k + 1]

        # --- Rebalance at start_idx ---
        lookback = min(20, start_idx)
        if lookback > 0:
            past_idx = start_idx - lookback
            mom = price.iloc[start_idx] / price.iloc[past_idx] - 1.0
        else:
            mom = pd.Series(0.0, index=price.columns)

        mom = mom.replace([np.inf, -np.inf], np.nan).dropna()
        if mom.empty:
            chosen = list(price.columns)[:top_n]
        else:
            ranked = mom.sort_values(ascending=False)
            chosen = list(ranked.index[:top_n])

        target_weights = pd.Series(0.0, index=price.columns)
        if chosen:
            w = 1.0 / len(chosen)
            w = min(w, max_per_position_pct or 1.0)
            target_weights.loc[chosen] = w

        # --- Apply daily returns until next rebalance ---
        rebalance_price = price.iloc[start_idx]
        trade_cost_total = 0.0
        for sym in price.columns:
            target_weight = float(target_weights.get(sym, 0.0))
            current_weight = float(current_weights.get(sym, 0.0))
            if abs(target_weight - current_weight) < 1e-9:
                continue

            trade_notional = (target_weight - current_weight) * equity
            side = "buy" if trade_notional > 0 else "sell"
            px = float(rebalance_price.get(sym, np.nan))
            if math.isnan(px) or px == 0:
                continue

            slip_cost = 0.0
            if slippage_model == "bps" and slippage_bps:
                slip_cost = abs(trade_notional) * (slippage_bps / 10000.0)

            commission = 0.0
            if trade_notional != 0.0:
                commission = float(commission_per_trade) + abs(trade_notional) * float(
                    commission_pct
                )

            trade_cost_total += slip_cost + commission
            qty = abs(trade_notional) / px if px else 0.0

            trades.append(
                {
                    "symbol": sym,
                    "side": side,
                    "notional": trade_notional,
                    "quantity": qty,
                    "price": px,
                    "commission": commission,
                    "slippage_cost": slip_cost,
                    "timestamp": dates[start_idx].isoformat(),
                }
            )

        if trade_cost_total:
            equity -= trade_cost_total
        current_weights = target_weights

        for j in range(start_idx, end_idx + 1):
            day_ret = float((daily_ret.iloc[j] * current_weights).sum())
            equity *= 1.0 + day_ret
            equity_series.iloc[j] = equity

    # -------------------------
    # 3) Benchmark buy & hold
    # -------------------------
    increment_yf_counter()
    bench_data = yf.download(
        benchmark,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
    )
    if bench_data.empty:
        raise ValueError(f"No price data for benchmark {benchmark}")

    if isinstance(bench_data.columns, pd.MultiIndex):
        bench_close = bench_data["Close"]
        if isinstance(bench_close, pd.DataFrame):
            bench_close = bench_close.iloc[:, 0]
    else:
        bench_close = bench_data["Close"]

    bench_close = bench_close.dropna()
    bench_norm = bench_close / bench_close.iloc[0]
    bench_eq = bench_norm * initial_capital

    # Align indices
    combined_index = equity_series.index.union(bench_eq.index)
    equity_series = equity_series.reindex(combined_index).ffill()
    bench_eq = bench_eq.reindex(combined_index).ffill()

    # -------------------------
    # 4) Portfolio summary
    # -------------------------
    start_val = float(equity_series.iloc[0])
    end_val = float(equity_series.iloc[-1])
    total_return = (end_val / start_val) - 1.0

    bench_start = float(bench_eq.iloc[0])
    bench_end = float(bench_eq.iloc[-1])
    bench_return = (bench_end / bench_start) - 1.0

    alpha = total_return - bench_return

    daily_ret_port = equity_series.pct_change().dropna()
    if not daily_ret_port.empty:
        avg_daily = float(daily_ret_port.mean())
        std_daily = float(daily_ret_port.std())
        ann_factor = math.sqrt(252.0)
        cagr = (1.0 + total_return) ** (252.0 / len(daily_ret_port)) - 1.0
        vol_annual = std_daily * ann_factor if std_daily > 0 else 0.0
        sharpe = (avg_daily / std_daily) * ann_factor if std_daily > 0 else 0.0
    else:
        cagr = 0.0
        vol_annual = 0.0
        sharpe = 0.0

    mdd = _max_drawdown(equity_series / start_val)

    equity_curve = [
        {"date": d.isoformat(), "value": float(v)} for d, v in equity_series.items()
    ]
    bench_curve = [
        {"date": d.isoformat(), "value": float(v)} for d, v in bench_eq.items()
    ]

    mdd_duration = _max_drawdown_duration(equity_series / start_val)

    summary = {
        "initial_capital": float(initial_capital),
        "final_value": end_val,
        "total_return": total_return,
        "benchmark_return": bench_return,
        "alpha": alpha,
        "cagr": cagr,
        "volatility_annual": vol_annual,
        "volatility_annualized": vol_annual,
        "sharpe_like": sharpe,
        "sharpe_ratio": sharpe,
        "max_drawdown": mdd,
        "max_drawdown_duration_bars": mdd_duration,
        "trades": trades,
    }

    # -------------------------
    # 5) Per-ticker buy & hold stats
    # -------------------------
    per_ticker_stats: List[Dict[str, Any]] = []
    ann_factor = math.sqrt(252.0)

    for sym in norm.columns:
        col_norm = norm[sym].dropna()
        if col_norm.empty:
            continue

        total_ret = float(col_norm.iloc[-1] - 1.0)

        series_price = price[sym].dropna()
        daily = series_price.pct_change().dropna()

        if not daily.empty:
            avg_daily = float(daily.mean())
            std_daily = float(daily.std())
            vol_annual_sym = std_daily * ann_factor if std_daily > 0 else 0.0
            sharpe_like = (avg_daily / std_daily) * ann_factor if std_daily > 0 else 0.0
        else:
            vol_annual_sym = 0.0
            sharpe_like = 0.0

        mdd_sym = _max_drawdown(col_norm)

        per_ticker_stats.append(
            {
                "symbol": sym,
                "total_return": total_ret,
                "volatility_annual": vol_annual_sym,
                "sharpe_like": sharpe_like,
                "max_drawdown": mdd_sym,
            }
        )

    return BacktestResult(
        tickers=tickers,
        start=start,
        end=end,
        equity_curve=equity_curve,
        benchmark_symbol=benchmark,
        benchmark_curve=bench_curve,
        summary=summary,
        per_ticker=per_ticker_stats,
    )
