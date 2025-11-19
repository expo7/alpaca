import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
x = os.getenv("HTTP_PROXY")

print(x)
# import pandas as pd
# import pandas_ta as ta
# import yfinance as yf

# def _safe_first_like(df_or_none, like: str, index) -> pd.Series:
#     """Return the first column that contains `like`, or an empty float series aligned to index."""
#     if isinstance(df_or_none, pd.DataFrame) and not df_or_none.empty:
#         sub = df_or_none.filter(like=like)
#         if not sub.empty:
#             return sub.iloc[:, 0]
#     return pd.Series(index=index, dtype="float64")

# def technical_score(symbol: str, period="6mo", interval="1d") -> tuple[float, dict]:
#     df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
#     if df is None or df.empty:
#         return 0.0, {"error": "no_data"}

#     # make sure expected columns exist
#     for col in ("Open", "High", "Low", "Close", "Volume"):
#         if col not in df.columns:
#             return 0.0, {"error": f"missing_column:{col}"}

#     # require enough history
#     if len(df) < 60:
#         return 0.0, {"error": "insufficient_data"}

#     # Indicators (robust to pandas_ta version differences)
#     df["EMA20"] = ta.ema(df["Close"], length=20)
#     df["EMA50"] = ta.ema(df["Close"], length=50)
#     df["EMA200"] = ta.ema(df["Close"], length=200)
#     adx_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
#     df["ADX"] = _safe_first_like(adx_df, "ADX", df.index)  # e.g., "ADX_14"

#     rsi = ta.rsi(df["Close"], length=14)
#     df["RSI"] = rsi if rsi is not None else pd.Series(index=df.index, dtype="float64")

#     df["ROC"] = ta.roc(df["Close"], length=14) or pd.Series(index=df.index, dtype="float64")

#     stoch_df = ta.stoch(df["High"], df["Low"], df["Close"])
#     df["STOCHK"] = _safe_first_like(stoch_df, "STOCHk", df.index)  # e.g., "STOCHk_14_3_3"

#     macd_df = ta.macd(df["Close"])
#     df["MACDh"] = _safe_first_like(macd_df, "MACDh", df.index)     # e.g., "MACDh_12_26_9"

#     df["OBV"] = ta.obv(df["Close"], df["Volume"]) or pd.Series(index=df.index, dtype="float64")
#     df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"]) or pd.Series(index=df.index, dtype="float64")
#     print(df["ATR"])

#     bb = ta.bbands(df["Close"])
#     bbl = _safe_first_like(bb, "BBL", df.index)                     # e.g., "BBL_20_2.0"
#     bbu = _safe_first_like(bb, "BBU", df.index)                     # e.g., "BBU_20_2.0"
#     df["BBL"] = bbl
#     df["BBW"] = (bbu - bbl) / df["Close"]

#     # drop rows with early NaNs from indicators; ensure we still have data
#     work = df.dropna()
#     if work.empty:
#         return 0.0, {"error": "all_indicators_nan"}

#     last = work.iloc[-1]
#     comp = {}
#     score = 0.0

#     # Trend (35)
#     trend_pts = 0
#     if last["Close"] > last["EMA20"] > last["EMA50"] > last["EMA200"]:
#         trend_pts += 20
#     if pd.notna(last.get("ADX")) and last["ADX"] > 25:
#         trend_pts += 10
#     if pd.notna(last.get("MACDh")) and last["MACDh"] > 0:
#         trend_pts += 5
#     score += trend_pts * 0.35
#     comp["trend_raw"] = trend_pts

#     # Momentum (25)
#     mom_pts = 0
#     if pd.notna(last.get("RSI")) and 50 < last["RSI"] < 70:
#         mom_pts += 10
#     if pd.notna(last.get("RSI")) and last["RSI"] < 30:
#         mom_pts += 10
#     if pd.notna(last.get("ROC")) and last["ROC"] > 0:
#         mom_pts += 5
#     if pd.notna(last.get("STOCHK")) and last["STOCHK"] > 50:
#         mom_pts += 5
#     score += mom_pts * 0.25
#     comp["momentum_raw"] = mom_pts

#     # Volume (20)
#     vol_pts = 0
#     if (work["OBV"].iloc[-1] > work["OBV"].iloc[-20]) if len(work) >= 20 else False:
#         vol_pts += 10
#     if work["Volume"].iloc[-1] > 1.5 * work["Volume"].tail(20).mean():
#         vol_pts += 10
#     score += vol_pts * 0.20
#     comp["volume_raw"] = vol_pts

#     # Volatility / Risk (10)
#     volty_pts = 0
#     if pd.notna(last.get("ATR")) and last["ATR"] > work["ATR"].tail(50).mean():
#         volty_pts += 5
#     if pd.notna(work["BBW"].iloc[-1]) and work["BBW"].iloc[-1] > work["BBW"].quantile(0.75):
#         volty_pts += 5
#     score += volty_pts * 0.10
#     comp["volatility_raw"] = volty_pts

#     # Mean Reversion (10)
#     mr_pts = 0
#     if pd.notna(last.get("BBL")) and last["Close"] > last["BBL"]:
#         mr_pts += 5
#     if (work["RSI"].tail(5) < 30).any() and last["Close"] > last["EMA50"]:
#         mr_pts += 5
#     score += mr_pts * 0.10
#     comp["meanreversion_raw"] = mr_pts

#     return round(score, 2), comp
# # technical_score(symbol="msft", period="6mo", interval="1d")

# df = yf.download('msft', period='6mo', interval='1d', auto_adjust=False, progress=False)
#    # Indicators (robust to pandas_ta version differences)
# df["EMA20"] = ta.ema(df["Close"], length=20)
# df["EMA50"] = ta.ema(df["Close"], length=50)
# df["EMA200"] = ta.ema(df["Close"], length=200)
# print(df.head())
