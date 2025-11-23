import json
import math
import warnings
import tempfile
from pathlib import Path
import os
import pandas as pd
import yfinance as yf
from django.core.cache import cache
from yfinance import cache as yf_cache
from ta import add_all_ta_features
from .metrics import increment_yf_counter

_YF_CACHE_DIR = Path(tempfile.gettempdir()) / "yfinance-cache"
try:
    _YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
try:
    yf_cache.set_cache_location(str(_YF_CACHE_DIR))
except Exception:
    pass

_PROXY_URL = (
    os.environ.get("WEBSHARE_PROXY")
    or os.environ.get("HTTPS_PROXY")
    or os.environ.get("HTTP_PROXY")
)
if _PROXY_URL:
    try:
        from yfinance import data as yf_data

        yf_data.YfData()._set_proxy(_PROXY_URL)
    except Exception:
        pass

warnings.filterwarnings("ignore")

_SCORE_CACHE_TTL = 60 * 15  # align with ranker.services CACHE_TTL


# ---------- helpers ----------
def _nz(x, default=None):
    return default if (x is None or (isinstance(x, float) and math.isnan(x))) else x


def _py(x):
    """Convert numpy/pandas scalars/NaN to plain Python types for JSONField."""
    try:
        if hasattr(x, "item"):
            return x.item()
        if pd.isna(x):
            return None
    except Exception:
        pass
    return x


def _tail_mean(series, n):
    s = series.tail(n).dropna()
    return float(s.mean()) if len(s) else None


# ---------- TECH: consumes df already enriched by `ta` ----------
def _technical_components(frame: pd.DataFrame, weights: dict):
    last = frame.iloc[-1]
    close = _nz(last.get("Close"))
    ema_fast = _nz(last.get("trend_ema_fast"))
    ema_slow = _nz(last.get("trend_ema_slow"))
    sma_fast = _nz(last.get("trend_sma_fast"))
    sma_slow = _nz(last.get("trend_sma_slow"))
    adx = _nz(last.get("trend_adx"))
    macd_diff = _nz(last.get("trend_macd_diff"))
    rsi = _nz(last.get("momentum_rsi"))
    roc = _nz(last.get("momentum_roc"))
    stoch = _nz(last.get("momentum_stoch"))
    obv = _nz(last.get("volume_obv"))
    atr = _nz(last.get("volatility_atr"))
    bbw = _nz(last.get("volatility_bbw"))
    bbl = _nz(last.get("volatility_bbl"))
    bbh = _nz(last.get("volatility_bbh"))
    volume = _nz(last.get("Volume"))

    score = 0.0
    comp = {}

    trend_pts = 0
    if close is not None and ema_fast is not None and ema_slow is not None:
        if close > ema_fast > ema_slow:
            trend_pts += 20
    elif close is not None and sma_fast is not None and sma_slow is not None:
        if close > sma_fast > sma_slow:
            trend_pts += 20
    if adx is not None and adx > 25:
        trend_pts += 10
    if macd_diff is not None and macd_diff > 0:
        trend_pts += 5
    score += trend_pts * float(weights["trend"])
    comp["trend_raw"] = trend_pts

    mom_pts = 0
    if rsi is not None and 50 < rsi < 70:
        mom_pts += 10
    if rsi is not None and rsi < 30:
        mom_pts += 10
    if roc is not None and roc > 0:
        mom_pts += 5
    if stoch is not None and stoch > 50:
        mom_pts += 5
    score += mom_pts * float(weights["momentum"])
    comp["momentum_raw"] = mom_pts

    vol_pts = 0
    if "volume_obv" in frame.columns and len(frame) >= 21:
        try:
            if frame["volume_obv"].iloc[-1] > frame["volume_obv"].iloc[-21]:
                vol_pts += 10
        except Exception:
            pass
    if "Volume" in frame.columns and len(frame) >= 20:
        vmean20 = _tail_mean(frame["Volume"], 20)
        if vmean20 and volume and volume > 1.5 * vmean20:
            vol_pts += 10
    score += vol_pts * float(weights["volume"])
    comp["volume_raw"] = vol_pts

    volty_pts = 0
    if "volatility_atr" in frame.columns and len(frame) >= 50:
        atr_mean50 = _tail_mean(frame["volatility_atr"], 50)
        if atr is not None and atr_mean50 and atr > atr_mean50:
            volty_pts += 5
    if "volatility_bbw" in frame.columns and len(frame) >= 30:
        bbw_q75 = frame["volatility_bbw"].tail(100).quantile(0.75)
        if bbw is not None and bbw_q75 is not None and bbw > bbw_q75:
            volty_pts += 5
    score += volty_pts * float(weights["volatility"])
    comp["volatility_raw"] = volty_pts

    mr_pts = 0
    if bbl is not None and close is not None and close > bbl:
        mr_pts += 5
    rsi_recent_oversold = False
    if "momentum_rsi" in frame.columns:
        rsi_recent_oversold = (frame["momentum_rsi"].tail(5) < 30).any()
    reclaimed_trend = False
    if ema_slow is not None and close is not None:
        reclaimed_trend = close > ema_slow
    elif sma_slow is not None and close is not None:
        reclaimed_trend = close > sma_slow
    if rsi_recent_oversold and reclaimed_trend:
        mr_pts += 5
    score += mr_pts * float(weights["meanreversion"])
    comp["meanreversion_raw"] = mr_pts

    score = max(0.0, min(100.0, round(float(score), 2)))
    comp.update(
        {
            "ta_weights": {k: float(v) for k, v in weights.items()},
            "close": _py(close),
            "ema_fast": _py(ema_fast),
            "ema_slow": _py(ema_slow),
            "adx": _py(adx),
            "macd_diff": _py(macd_diff),
            "rsi": _py(rsi),
            "roc": _py(roc),
            "stoch": _py(stoch),
            "obv": _py(obv),
            "atr": _py(atr),
            "bbw": _py(bbw),
            "bbl": _py(bbl),
            "bbh": _py(bbh),
        }
    )
    return score, comp


def _technical_deltas(cur, prev):
    if not prev:
        return {}
    keys = [
        "trend_raw",
        "momentum_raw",
        "volume_raw",
        "volatility_raw",
        "meanreversion_raw",
    ]
    deltas = {}
    for key in keys:
        cv = cur.get(key)
        pv = prev.get(key)
        if cv is None or pv is None:
            deltas[key] = None
            continue
        try:
            deltas[key] = round(float(cv) - float(pv), 2)
        except (TypeError, ValueError):
            deltas[key] = None
    return deltas


def technical_score_from_ta(df: pd.DataFrame, *, weights=None) -> tuple[float, dict]:
    """
    weights = {"trend":0.35, "momentum":0.25, "volume":0.20, "volatility":0.10, "meanreversion":0.10}
    """
    if weights is None:
        weights = {
            "trend": 0.35,
            "momentum": 0.25,
            "volume": 0.20,
            "volatility": 0.10,
            "meanreversion": 0.10,
        }

    if df is None or df.empty:
        return 0.0, {"error": "no_data"}

    work = df.dropna()
    if work.empty:
        return 0.0, {"error": "all_nan_after_indicators"}

    score, comp = _technical_components(work, weights)

    prev_comp = None
    prev_score = None
    if len(work) >= 2:
        prev_frame = work.iloc[:-1]
        if not prev_frame.empty:
            prev_score, prev_comp = _technical_components(prev_frame, weights)

    if prev_comp:
        comp["deltas"] = _technical_deltas(comp, prev_comp)
        comp["score_delta"] = round(score - prev_score, 2)
    else:
        comp["deltas"] = {}
        comp["score_delta"] = None

    return score, comp


# ---------- TECH: fetch + enrich + score ----------
def technical_score(
    symbol: str, period="6mo", interval="1d", *, ta_weights=None
) -> tuple[float, dict]:
    cache_key = "ranker:technical:{symbol}:{weights}".format(
        symbol=symbol.upper(),
        weights=json.dumps(ta_weights, sort_keys=True) if ta_weights else "default",
    )
    cached = cache.get(cache_key)
    if cached:
        return cached

    increment_yf_counter()
    df = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return 0.0, {"error": "no_data"}
    df = add_all_ta_features(
        df,
        open="Open",
        high="High",
        low="Low",
        close="Close",
        volume="Volume",
        fillna=True,
    )
    result = technical_score_from_ta(df, weights=ta_weights)
    cache.set(cache_key, result, _SCORE_CACHE_TTL)
    return result


# ---------- FUNDAMENTALS ----------
def fundamental_score(symbol: str) -> tuple[float, dict]:
    cache_key = f"ranker:fundamental:{symbol.upper()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    increment_yf_counter()
    tkr = yf.Ticker(symbol)
    info = tkr.info or {}

    pe = info.get("forwardPE")
    peg = info.get("pegRatio")
    ps = info.get("priceToSalesTrailing12Months")
    ev_ebitda = info.get("enterpriseToEbitda")
    net_margin = info.get("profitMargins")
    roe = info.get("returnOnEquity")
    roic_proxy = info.get("returnOnAssets")
    revenue_growth = info.get("revenueGrowth")
    eps_growth = info.get("earningsQuarterlyGrowth")
    debt_equity = info.get("debtToEquity")
    current_ratio = info.get("currentRatio")
    free_cashflow = info.get("freeCashflow")

    comp, score = {}, 0

    # Valuation (30)
    val = 0
    if pe is not None and pe < 20:
        val += 10
    if peg is not None and peg < 1.5:
        val += 10
    if ev_ebitda is not None and ev_ebitda < 12:
        val += 5
    if ps is not None and ps < 4:
        val += 5
    score += val * 0.30
    comp["valuation_raw"] = val

    # Profitability (30)
    prof = 0
    if net_margin is not None and net_margin > 0.10:
        prof += 10
    if roe is not None and roe > 0.12:
        prof += 10
    if roic_proxy is not None and roic_proxy > 0.08:
        prof += 10
    score += prof * 0.30
    comp["profitability_raw"] = prof

    # Growth (20)
    growth = 0
    if revenue_growth is not None and revenue_growth > 0.10:
        growth += 10
    if eps_growth is not None and eps_growth > 0.10:
        growth += 10
    score += growth * 0.20
    comp["growth_raw"] = growth

    # Health (10)
    health = 0
    if debt_equity is not None and debt_equity < 1:
        health += 5
    if current_ratio is not None and current_ratio > 1.2:
        health += 5
    score += health * 0.10
    comp["health_raw"] = health

    # Efficiency (10)
    eff = 0
    if free_cashflow is not None and free_cashflow > 0:
        eff += 5
    score += eff * 0.10
    comp["efficiency_raw"] = eff

    result = round(float(score), 2), comp
    cache.set(cache_key, result, _SCORE_CACHE_TTL)
    return result


# ---------- BLEND ----------
def blended_score(
    symbol: str, tech_weight=0.5, fundamental_weight=0.5, *, ta_weights=None
):
    t_score, t_comp = technical_score(symbol, ta_weights=ta_weights)
    f_score, f_comp = fundamental_score(symbol)
    final = round(tech_weight * t_score + fundamental_weight * f_score, 2)
    components = {
        "technical": t_comp,
        "fundamental": f_comp,
        "weights": {"tech": float(tech_weight), "fund": float(fundamental_weight)},
    }
    return final, t_score, f_score, components


# import math
# import warnings
# import pandas as pd
# import yfinance as yf
# from ta import add_all_ta_features

# warnings.filterwarnings("ignore")

# # ---------- helpers ----------
# def _nz(x, default=None):
#     return default if (x is None or (isinstance(x, float) and math.isnan(x))) else x

# def _py(x):
#     """Convert numpy scalars/NaN to plain Python types for JSONField."""
#     try:
#         # pandas/np scalars often have .item()
#         if hasattr(x, "item"):
#             return x.item()
#         if pd.isna(x):
#             return None
#     except Exception:
#         pass
#     return x

# def _tail_mean(series, n):
#     s = series.tail(n).dropna()
#     return float(s.mean()) if len(s) else None

# # ---------- TECH: consumes df already enriched by `ta` ----------
# def technical_score_from_ta(df: pd.DataFrame,*,weights=None) -> tuple[float, dict]:
#     if df is None or df.empty:
#         return 0.0, {"error": "no_data"}

#     work = df.dropna()
#     if work.empty:
#         return 0.0, {"error": "all_nan_after_indicators"}

#     last = work.iloc[-1]

#     # Pull fields
#     close = _nz(last.get("Close"))
#     ema_fast = _nz(last.get("trend_ema_fast"))
#     ema_slow = _nz(last.get("trend_ema_slow"))
#     sma_fast = _nz(last.get("trend_sma_fast"))
#     sma_slow = _nz(last.get("trend_sma_slow"))
#     adx = _nz(last.get("trend_adx"))
#     macd_diff = _nz(last.get("trend_macd_diff"))
#     rsi = _nz(last.get("momentum_rsi"))
#     roc = _nz(last.get("momentum_roc"))
#     stoch = _nz(last.get("momentum_stoch"))
#     obv = _nz(last.get("volume_obv"))
#     atr = _nz(last.get("volatility_atr"))
#     bbw = _nz(last.get("volatility_bbw"))
#     bbl = _nz(last.get("volatility_bbl"))
#     bbh = _nz(last.get("volatility_bbh"))
#     volume = _nz(last.get("Volume"))

#     score = 0.0
#     comp = {}

#     # 1) Trend (35)
#     trend_pts = 0
#     if (close is not None and ema_fast is not None and ema_slow is not None):
#         if close > ema_fast > ema_slow:
#             trend_pts += 20
#     elif (close is not None and sma_fast is not None and sma_slow is not None):
#         if close > sma_fast > sma_slow:
#             trend_pts += 20
#     if adx is not None and adx > 25:
#         trend_pts += 10
#     if macd_diff is not None and macd_diff > 0:
#         trend_pts += 5
#     score += trend_pts * 0.35
#     comp["trend_raw"] = trend_pts

#     # 2) Momentum (25)
#     mom_pts = 0
#     if rsi is not None and 50 < rsi < 70:
#         mom_pts += 10
#     if rsi is not None and rsi < 30:
#         mom_pts += 10
#     if roc is not None and roc > 0:
#         mom_pts += 5
#     if stoch is not None and stoch > 50:
#         mom_pts += 5
#     score += mom_pts * 0.25
#     comp["momentum_raw"] = mom_pts

#     # 3) Volume (20)
#     vol_pts = 0
#     if "volume_obv" in work.columns and len(work) >= 21:
#         try:
#             if work["volume_obv"].iloc[-1] > work["volume_obv"].iloc[-21]:
#                 vol_pts += 10
#         except Exception:
#             pass
#     if "Volume" in work.columns and len(work) >= 20:
#         vmean20 = _tail_mean(work["Volume"], 20)
#         if vmean20 and volume and volume > 1.5 * vmean20:
#             vol_pts += 10
#     score += vol_pts * 0.20
#     comp["volume_raw"] = vol_pts

#     # 4) Volatility / Risk (10)
#     volty_pts = 0
#     if "volatility_atr" in work.columns and len(work) >= 50:
#         atr_mean50 = _tail_mean(work["volatility_atr"], 50)
#         if atr is not None and atr_mean50 and atr > atr_mean50:
#             volty_pts += 5
#     if "volatility_bbw" in work.columns and len(work) >= 30:
#         bbw_q75 = work["volatility_bbw"].tail(100).quantile(0.75)
#         if bbw is not None and bbw_q75 is not None and bbw > bbw_q75:
#             volty_pts += 5
#     score += volty_pts * 0.10
#     comp["volatility_raw"] = volty_pts

#     # 5) Mean Reversion (10)
#     mr_pts = 0
#     if (bbl is not None and close is not None and close > bbl):
#         mr_pts += 5
#     rsi_recent_oversold = False
#     if "momentum_rsi" in work.columns:
#         rsi_recent_oversold = (work["momentum_rsi"].tail(5) < 30).any()
#     reclaimed_trend = False
#     if ema_slow is not None and close is not None:
#         reclaimed_trend = close > ema_slow
#     elif sma_slow is not None and close is not None:
#         reclaimed_trend = close > sma_slow
#     if rsi_recent_oversold and reclaimed_trend:
#         mr_pts += 5
#     score += mr_pts * 0.10
#     comp["meanreversion_raw"] = mr_pts

#     # Finalize
#     score = max(0.0, min(100.0, round(float(score), 2)))
#     comp.update({
#         "close": _py(close), "ema_fast": _py(ema_fast), "ema_slow": _py(ema_slow),
#         "adx": _py(adx), "macd_diff": _py(macd_diff), "rsi": _py(rsi),
#         "roc": _py(roc), "stoch": _py(stoch), "obv": _py(obv),
#         "atr": _py(atr), "bbw": _py(bbw), "bbl": _py(bbl), "bbh": _py(bbh),
#     })
#     return score, comp

# # ---------- TECH: fetch + enrich + score ----------
# def technical_score(symbol: str, period="6mo", interval="1d") -> tuple[float, dict]:
#     # Use 1y daily to get enough warmup for many indicators
#     df = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=False)
#     if df is None or df.empty:
#         return 0.0, {"error": "no_data"}
#     df = add_all_ta_features(
#         df, open="Open", high="High", low="Low", close="Close", volume="Volume", fillna=True
#     )
#     return technical_score_from_ta(df)

# # ---------- FUNDAMENTALS ----------
# def fundamental_score(symbol: str) -> tuple[float, dict]:
#     tkr = yf.Ticker(symbol)
#     info = tkr.info or {}

#     pe = info.get("forwardPE")
#     peg = info.get("pegRatio")
#     ps = info.get("priceToSalesTrailing12Months")
#     ev_ebitda = info.get("enterpriseToEbitda")
#     net_margin = info.get("profitMargins")
#     roe = info.get("returnOnEquity")
#     roic_proxy = info.get("returnOnAssets")
#     revenue_growth = info.get("revenueGrowth")
#     eps_growth = info.get("earningsQuarterlyGrowth")
#     debt_equity = info.get("debtToEquity")
#     current_ratio = info.get("currentRatio")
#     free_cashflow = info.get("freeCashflow")

#     comp, score = {}, 0

#     # Valuation (30)
#     val = 0
#     if pe is not None and pe < 20: val += 10
#     if peg is not None and peg < 1.5: val += 10
#     if ev_ebitda is not None and ev_ebitda < 12: val += 5
#     if ps is not None and ps < 4: val += 5
#     score += val * 0.30
#     comp["valuation_raw"] = val

#     # Profitability (30)
#     prof = 0
#     if net_margin is not None and net_margin > 0.10: prof += 10
#     if roe is not None and roe > 0.12: prof += 10
#     if roic_proxy is not None and roic_proxy > 0.08: prof += 10
#     score += prof * 0.30
#     comp["profitability_raw"] = prof

#     # Growth (20)
#     growth = 0
#     if revenue_growth is not None and revenue_growth > 0.10: growth += 10
#     if eps_growth is not None and eps_growth > 0.10: growth += 10
#     score += growth * 0.20
#     comp["growth_raw"] = growth

#     # Health (10)
#     health = 0
#     if debt_equity is not None and debt_equity < 1: health += 5
#     if current_ratio is not None and current_ratio > 1.2: health += 5
#     score += health * 0.10
#     comp["health_raw"] = health

#     # Efficiency (10)
#     eff = 0
#     if free_cashflow is not None and free_cashflow > 0: eff += 5
#     score += eff * 0.10
#     comp["efficiency_raw"] = eff

#     # Coerce to python types
#     for k, v in list(comp.items()):
#         comp[k] = _py(v)
#     return round(float(score), 2), comp

# # ---------- BLEND ----------
# def blended_score(symbol: str, tech_weight=0.5, fundamental_weight=0.5):
#     t_score, t_comp = technical_score(symbol)
#     f_score, f_comp = fundamental_score(symbol)
#     final = round(tech_weight * t_score + fundamental_weight * f_score, 2)
#     components = {
#         "technical": t_comp,
#         "fundamental": f_comp,
#         "weights": {"tech": float(tech_weight), "fund": float(fundamental_weight)},
#     }
#     return final, t_score, f_score, components
