# ranker/backtest.py

import logging
import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from decimal import Decimal

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
    if series.empty:
        return 0

    peak = float(series.iloc[0])
    duration = 0
    max_duration = 0
    for value in series:
        if value >= peak:
            peak = float(value)
            duration = 0
        else:
            duration += 1
            if duration > max_duration:
                max_duration = duration
    return int(max_duration)


def _param_default(params: Dict[str, Any], key: str, fallback=None):
    val = params.get(key)
    if isinstance(val, dict):
        return val.get("default", fallback)
    return val if val is not None else fallback


def _eval_node(node: dict, indicators: dict, params: dict, dyn_params: dict) -> bool:
    if not node:
        return False
    node_type = (node.get("type") or "").lower()
    if node_type in {"and", "group"}:
        children = node.get("children") or []
        op = (node.get("op") or "and").lower()
        if op == "and":
            return all(_eval_node(ch, indicators, params, dyn_params) for ch in children)
        return any(_eval_node(ch, indicators, params, dyn_params) for ch in children)
    if node_type == "or":
        children = node.get("children") or []
        return any(_eval_node(ch, indicators, params, dyn_params) for ch in children)
    if node_type in {"condition", "indicator_condition", "position_condition"}:
        ind = node.get("indicator") or node.get("left")
        operator = (node.get("operator") or "").lower()
        left = indicators.get(ind)
        if left is None:
            return False
        val = None
        if "value_param" in node:
            vp = node.get("value_param")
            val = dyn_params.get(vp)
            if val is None:
                val = _param_default(params, vp)
        elif "value" in node:
            raw = node.get("value")
            if isinstance(raw, dict) and "param" in raw:
                val = _param_default(params, raw.get("param"))
            elif isinstance(raw, dict) and "value_param" in raw:
                val = _param_default(params, raw.get("value_param"))
            else:
                val = raw
        if val is None:
            return False
        try:
            left_f = float(left)
            right_f = float(val)
        except Exception:
            return False
        if operator in {"lt", "<"}:
            return left_f < right_f
        if operator in {"lte", "<="}:
            return left_f <= right_f
        if operator in {"gt", ">"}:
            return left_f > right_f
        if operator in {"gte", ">="}:
            return left_f >= right_f
        if operator in {"ne", "!="}:
            return left_f != right_f
        return left_f == right_f
    return False


def _compute_indicators(close_series: pd.Series, idx: int, params: dict) -> tuple[dict, dict]:
    window_slice = close_series.iloc[: idx + 1]
    indicators = {}
    dyn = {}
    price = window_slice.iloc[-1]
    indicators["close"] = price

    fast_len = _param_default(params, "fast_length")
    if fast_len and len(window_slice) >= int(fast_len):
        indicators["sma_fast"] = float(window_slice.tail(int(fast_len)).mean())

    slow_len = _param_default(params, "slow_length")
    if slow_len and len(window_slice) >= int(slow_len):
        slow_val = float(window_slice.tail(int(slow_len)).mean())
        indicators["sma_slow"] = slow_val
        dyn["slow_sma_value"] = slow_val

    rsi_len = _param_default(params, "rsi_period")
    if rsi_len and len(window_slice) >= int(rsi_len):
        delta = window_slice.diff()
        gain = delta.clip(lower=0).rolling(window=int(rsi_len)).mean()
        loss = -delta.clip(upper=0).rolling(window=int(rsi_len)).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.dropna()
        if not last_rsi.empty:
            indicators["rsi"] = float(last_rsi.iloc[-1])

    lb_high_len = _param_default(params, "lookback_high")
    if lb_high_len and len(window_slice) >= int(lb_high_len):
        high_val = float(window_slice.tail(int(lb_high_len)).max())
        dyn["lookback_high_level"] = high_val

    stop_len = _param_default(params, "stop_lookback")
    if stop_len and len(window_slice) >= int(stop_len):
        low_val = float(window_slice.tail(int(stop_len)).min())
        dyn["stop_level"] = low_val

    return indicators, dyn


def _run_strategy_spec_backtest(
    price: pd.DataFrame,
    tickers: List[str],
    benchmark: str,
    start: str,
    end: str,
    initial_capital: float,
    commission_per_trade: float,
    commission_pct: float,
    slippage_model_norm: str,
    slippage_bps: float,
    strategy_spec: Dict[str, Any],
) -> BacktestResult:
    params = strategy_spec.get("parameters") or {}
    entry_tree = strategy_spec.get("entry_tree") or {}
    exit_tree = strategy_spec.get("exit_tree") or {}
    dates = price.index
    equity_series = pd.Series(index=dates, dtype=float)
    equity = float(initial_capital)
    cash = float(initial_capital)
    positions: Dict[str, Dict[str, Any]] = {}
    trades: List[Dict[str, Any]] = []

    for i, dt in enumerate(dates):
        # process exits first
        for sym, pos in list(positions.items()):
            px = float(price.iloc[i].get(sym, np.nan))
            if math.isnan(px) or px == 0:
                continue
            indicators, dyn = _compute_indicators(price[sym], i, params)
            if exit_tree and _eval_node(exit_tree, indicators, params, dyn):
                proceeds = pos["qty"] * px
                cash += proceeds
                commission = float(commission_per_trade) + abs(proceeds) * float(commission_pct)
                slip_cost = abs(proceeds) * (slippage_bps / 10000.0) if slippage_model_norm == "bps" else 0.0
                cash -= commission + slip_cost
                days_held = None
                try:
                    entry_dt = pd.to_datetime(pos.get("entry_time"))
                    exit_dt = pd.to_datetime(dt)
                    if not pd.isna(entry_dt) and not pd.isna(exit_dt):
                        days_held = round(float((exit_dt - entry_dt).total_seconds()) / 86400.0, 2)
                except Exception:
                    days_held = None
                trades.append(
                    {
                        "symbol": sym,
                        "side": "sell",
                        "quantity": pos["qty"],
                        "entry_price": round(pos["entry_price"], 2) if pos["entry_price"] else pos["entry_price"],
                        "exit_price": round(px, 2),
                        "commission": round(commission, 2),
                        "slippage_cost": round(slip_cost, 2),
                        "entry_time": pos.get("entry_time"),
                        "exit_time": dt.isoformat(),
                        "pnl": round((proceeds - commission - slip_cost) - (pos["qty"] * pos["entry_price"]), 2),
                        "pnl_pct": round(((px - pos["entry_price"]) / pos["entry_price"]) if pos["entry_price"] else 0.0, 4),
                        "days_held": days_held,
                    }
                )
                del positions[sym]

        # process entries
        for sym in tickers:
            if sym in positions:
                continue
            px = float(price.iloc[i].get(sym, np.nan))
            if math.isnan(px) or px == 0:
                continue
            indicators, dyn = _compute_indicators(price[sym], i, params)
            if entry_tree and _eval_node(entry_tree, indicators, params, dyn):
                # equal-weight remaining cash
                allocation = cash / max(1, len(tickers))
                qty = allocation / px if px else 0.0
                if qty <= 0:
                    continue
                cost = qty * px
                commission = float(commission_per_trade) + cost * float(commission_pct)
                slip_cost = cost * (slippage_bps / 10000.0) if slippage_model_norm == "bps" else 0.0
                total_cost = cost + commission + slip_cost
                if cash < total_cost:
                    continue
                cash -= total_cost
                positions[sym] = {
                    "qty": qty,
                    "entry_price": px,
                    "entry_time": dt.isoformat(),
                }

        positions_value = 0.0
        for sym, pos in positions.items():
            px = float(price.iloc[i].get(sym, np.nan))
            if math.isnan(px) or px == 0:
                continue
            positions_value += pos["qty"] * px
        equity = cash + positions_value
        equity_series.iloc[i] = equity

    # close remaining positions at end
    if positions:
        last_dt = dates[-1]
        for sym, pos in list(positions.items()):
            px = float(price.iloc[-1].get(sym, np.nan))
            if math.isnan(px) or px == 0:
                continue
            proceeds = pos["qty"] * px
            commission = float(commission_per_trade) + abs(proceeds) * float(commission_pct)
            slip_cost = abs(proceeds) * (slippage_bps / 10000.0) if slippage_model_norm == "bps" else 0.0
            cash += proceeds - commission - slip_cost
            days_held = None
            try:
                entry_dt = pd.to_datetime(pos.get("entry_time"))
                exit_dt = pd.to_datetime(last_dt)
                if not pd.isna(entry_dt) and not pd.isna(exit_dt):
                    days_held = round(float((exit_dt - entry_dt).total_seconds()) / 86400.0, 2)
            except Exception:
                days_held = None
            trades.append(
                {
                    "symbol": sym,
                    "side": "sell",
                    "quantity": pos["qty"],
                    "entry_price": round(pos["entry_price"], 2) if pos["entry_price"] else pos["entry_price"],
                    "exit_price": round(px, 2),
                    "commission": round(commission, 2),
                    "slippage_cost": round(slip_cost, 2),
                    "entry_time": pos.get("entry_time"),
                    "exit_time": last_dt.isoformat(),
                    "pnl": round((proceeds - commission - slip_cost) - (pos["qty"] * pos["entry_price"]), 2),
                    "pnl_pct": round(((px - pos["entry_price"]) / pos["entry_price"]) if pos["entry_price"] else 0.0, 4),
                    "days_held": days_held,
                }
            )
            del positions[sym]
        equity = cash
        equity_series.iloc[-1] = equity

    # Benchmark
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

    combined_index = equity_series.index.union(bench_eq.index)
    equity_series = equity_series.reindex(combined_index).ffill()
    bench_eq = bench_eq.reindex(combined_index).ffill()

    start_val = float(equity_series.iloc[0])
    end_val = float(equity_series.iloc[-1])
    total_return = (end_val / start_val) - 1.0 if start_val else 0.0

    bench_start = float(bench_eq.iloc[0])
    bench_end = float(bench_eq.iloc[-1])
    bench_return = (bench_end / bench_start) - 1.0 if bench_start else 0.0

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

    mdd = _max_drawdown(equity_series / start_val) if start_val else 0.0
    mdd_duration = _max_drawdown_duration(equity_series / start_val) if start_val else 0

    equity_curve = [
        {"date": d.isoformat(), "value": float(v)} for d, v in equity_series.items()
    ]
    bench_curve = [
        {"date": d.isoformat(), "value": float(v)} for d, v in bench_eq.items()
    ]

    summary = {
        "initial_capital": round(float(initial_capital), 2),
        "final_value": round(end_val, 2),
        "total_return": round(total_return, 4),
        "benchmark_return": round(bench_return, 4),
        "alpha": round(total_return - bench_return, 4),
        "cagr": round(cagr, 4),
        "volatility_annual": round(vol_annual, 4),
        "volatility_annualized": round(vol_annual, 4),
        "sharpe_like": round(sharpe, 4),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(mdd, 4),
        "max_drawdown_duration_bars": mdd_duration,
        "final_cash": round(cash, 2),
        "final_positions_value": 0.0,
        "final_unrealized": 0.0,
        "trades": trades,
        "num_trades": len(trades),
    }

    norm = _normalize_price_df(price)
    per_ticker_stats: List[Dict[str, Any]] = []
    ann_factor = math.sqrt(252.0)
    for sym in norm.columns:
        col_norm = norm[sym].dropna()
        if col_norm.empty:
            continue
        total_ret = float(col_norm.iloc[-1] - 1.0)
        daily_ret = col_norm.pct_change().dropna()
        ann_ret = (1.0 + total_ret) ** (252.0 / len(daily_ret)) - 1.0 if not daily_ret.empty else total_ret
        vol = float(daily_ret.std()) * ann_factor if not daily_ret.empty else 0.0
        per_ticker_stats.append(
            {
                "symbol": sym,
                "total_return": total_ret,
                "annual_return": ann_ret,
                "volatility": vol,
                "sharpe_like": (ann_ret / vol) if vol > 0 else 0.0,
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

    if strategy_spec and _contains_event_condition(strategy_spec.get("entry_tree")):
        logger.warning(
            "event_condition found in entry_tree but events are not wired yet; treating as False."
        )
    if strategy_spec and _contains_event_condition(strategy_spec.get("exit_tree")):
        logger.warning(
            "event_condition found in exit_tree but events are not wired yet; treating as False."
        )
    slippage_model_norm = (slippage_model or "none").lower()

    # --- Clean & dedupe tickers ---
    tickers = sorted({t.upper() for t in tickers if t})
    if not tickers:
        raise ValueError("No valid tickers provided")

    if top_n is None:
        top_n = len(tickers)
    else:
        top_n = max(0, min(top_n, len(tickers)))
    if max_open_positions is not None and max_open_positions > 0:
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

    # -------------------------
    # Strategy-driven path (no momentum rebalance) when strategy_spec provided
    # -------------------------
    if strategy_spec:
        return _run_strategy_spec_backtest(
            price=price,
            tickers=tickers,
            benchmark=benchmark,
            start=start,
            end=end,
            initial_capital=initial_capital,
            commission_per_trade=commission_per_trade,
            commission_pct=commission_pct,
            slippage_model_norm=slippage_model_norm,
            slippage_bps=slippage_bps,
            strategy_spec=strategy_spec,
        )

    # -------------------------
    # 2) Momentum rebalance path (legacy)
    # -------------------------
    daily_ret = price.pct_change().fillna(0.0)

    # Normalized prices (for per-ticker stats later)
    norm = _normalize_price_df(price)

    dates = price.index
    n_days = len(dates)

    warmup_days = min(
        max(20, int(rebalance_days) if rebalance_days else 0),
        max(0, n_days - 1),
    )
    step = max(1, int(rebalance_days) if rebalance_days else 1)
    rebal_indices = list(range(warmup_days, n_days, step))
    if not rebal_indices:
        rebal_indices = [0, n_days - 1]
    if rebal_indices[0] != 0 and warmup_days < n_days - 1:
        rebal_indices = [warmup_days] + rebal_indices
    if rebal_indices[0] != 0 and warmup_days >= n_days - 1:
        rebal_indices = [0] + rebal_indices
    if rebal_indices[-1] != n_days - 1:
        rebal_indices.append(n_days - 1)

    equity_series = pd.Series(index=dates, dtype=float)
    equity = float(initial_capital)
    current_weights = pd.Series(0.0, index=price.columns)
    trades: List[Dict[str, Any]] = []

    # Hold cash during warmup so early days have equity recorded
    first_rebalance_idx = rebal_indices[0]
    for j in range(0, first_rebalance_idx):
        equity_series.iloc[j] = equity

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

        # --- Rebalance trades at start_idx ---
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
            if math.isnan(px) or px == 0.0:
                continue

            slip_cost = 0.0
            if slippage_model_norm == "bps" and slippage_bps:
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
                    "entry_price": px,
                    "commission": commission,
                    "slippage_cost": slip_cost,
                    "timestamp": dates[start_idx].isoformat(),
                }
            )

        if trade_cost_total:
            equity -= trade_cost_total

        current_weights = target_weights

        # --- Apply daily returns until next rebalance ---
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
    mdd_duration = _max_drawdown_duration(equity_series / start_val)

    # Attach end-of-backtest prices/timestamps to trades for display
    last_prices = price.iloc[-1]
    last_ts = dates[-1].isoformat()
    for t in trades:
        sym = t.get("symbol")
        px = float(last_prices.get(sym, np.nan)) if sym in last_prices else float("nan")
        if not math.isnan(px):
            t["exit_price"] = px
        t["exit_time"] = last_ts

    equity_curve = [
        {"date": d.isoformat(), "value": float(v)} for d, v in equity_series.items()
    ]
    bench_curve = [
        {"date": d.isoformat(), "value": float(v)} for d, v in bench_eq.items()
    ]

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
        "num_trades": len(trades),
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
