"""
pipeline/indicators.py
──────────────────────
Technical indicators for the 10-confirmation signal.

Public API
──────────
  add_indicators(df) → pd.DataFrame
  compute_adx(df, period) → pd.Series
"""

import numpy  as np
import pandas as pd


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder-smoothed Average Directional Index (ADX).
    Uses alpha = 1/period (Wilder smoothing).
    """
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]
    alpha = 1.0 / period

    tr = pd.concat(
        [high - low,
         (high - close.shift(1)).abs(),
         (low  - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)

    up   = high - high.shift(1)
    down = low.shift(1) - low

    plus_dm  = up.where(  (up > down) & (up > 0),   0.0)
    minus_dm = down.where((down > up) & (down > 0),  0.0)

    atr      = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm( alpha=alpha, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr

    denom = (plus_di + minus_di).replace(0, np.nan)
    dx    = 100 * (plus_di - minus_di).abs() / denom
    return dx.ewm(alpha=alpha, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add EMA20, EMA200, RSI, MACD, MACD_Signal, MACD_Hist, ADX,
    Vol_SMA20, Momentum, Volatility to the DataFrame.
    """
    out = df.copy()

    out["EMA20"]  = out["Close"].ewm(span=20,  adjust=False).mean()
    out["EMA200"] = out["Close"].ewm(span=200, adjust=False).mean()

    alpha_rsi = 1.0 / 14
    delta     = out["Close"].diff()
    gain      = delta.clip(lower=0)
    loss      = (-delta.clip(upper=0))
    avg_gain  = gain.ewm(alpha=alpha_rsi, adjust=False).mean()
    avg_loss  = loss.ewm(alpha=alpha_rsi, adjust=False).mean()
    rs        = avg_gain / (avg_loss + 1e-10)
    out["RSI"] = 100 - (100 / (1 + rs))

    ema12               = out["Close"].ewm(span=12, adjust=False).mean()
    ema26               = out["Close"].ewm(span=26, adjust=False).mean()
    out["MACD"]         = ema12 - ema26
    out["MACD_Signal"]  = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_Hist"]    = out["MACD"] - out["MACD_Signal"]

    out["ADX"]       = compute_adx(out, period=14)
    out["Vol_SMA20"] = out["Volume"].rolling(20).mean()
    out["Momentum"]  = (out["Close"] / out["Close"].shift(24) - 1) * 100
    out["Volatility"] = out["Returns"].rolling(24).std() * np.sqrt(24) * 100

    return out
