"""
strategy/signals.py
───────────────────
Score 10 confirmation signals and generate trade signal (LONG/SHORT/NEUTRAL).
Provides get_ticker_data() — the main public API for the full pipeline.

Public API
──────────
  get_ticker_data(ticker, period, interval, n_states, rand_seed) → dict
  score_signals(df) → pd.DataFrame
  CONFIRM_COLS   — list of 10 confirmation column names
  CONFIRM_LABELS — {col_name: human_readable_label}
"""

import warnings
import numpy  as np
import pandas as pd

from pipeline.download   import download_ohlcv, PERIOD, INTERVAL
from pipeline.features   import engineer_features
from pipeline.indicators import add_indicators
from models.hmm          import fit_hmm, N_STATES, RANDOM_SEED

warnings.filterwarnings("ignore")

CONFIRM_COLS = [
    "C1_RSI_lt_80",
    "C2_Mom_gt_1p5",
    "C3_Vol_lt_6",
    "C4_MACD_near_pos",
    "C5_Vol_gt_SMA",
    "C6_ADX_gt_30",
    "C7_Price_gt_EMA20",
    "C8_Price_gt_EMA200",
    "C9_MACD_gt_Signal",
    "C10_RSI_gt_20",
]

CONFIRM_LABELS = {
    "C1_RSI_lt_80":       "RSI < 80  (not overbought)",
    "C2_Mom_gt_1p5":      "Momentum > 1.5%  (24-hr)",
    "C3_Vol_lt_6":        "Volatility < 6%  (24-hr realised)",
    "C4_MACD_near_pos":   "MACD nearing positive (histogram > -0.1% of price)",
    "C5_Vol_gt_SMA":      "Volume > 20-bar SMA",
    "C6_ADX_gt_30":       "ADX > 30  (strong trend)",
    "C7_Price_gt_EMA20":  "Price > EMA 20",
    "C8_Price_gt_EMA200": "Price > EMA 200",
    "C9_MACD_gt_Signal":  "MACD > Signal line  (bullish cross)",
    "C10_RSI_gt_20":      "RSI > 20  (not deeply oversold)",
}

_INDICATOR_COLS = [
    "EMA20", "EMA200", "RSI", "MACD", "MACD_Signal",
    "ADX", "Vol_SMA20", "Momentum", "Volatility",
]


def score_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 10 boolean confirmations, sum into Confirmations, assign Signal."""
    out = df.copy()

    out["C1_RSI_lt_80"]       = out["RSI"] < 80
    out["C2_Mom_gt_1p5"]      = out["Momentum"] > 1.5
    out["C3_Vol_lt_6"]        = out["Volatility"] < 6.0
    out["C4_MACD_near_pos"]   = out["MACD_Hist"] > -(out["Close"] * 0.001)
    out["C5_Vol_gt_SMA"]      = out["Volume"] > out["Vol_SMA20"]
    out["C6_ADX_gt_30"]       = out["ADX"] > 30
    out["C7_Price_gt_EMA20"]  = out["Close"] > out["EMA20"]
    out["C8_Price_gt_EMA200"] = out["Close"] > out["EMA200"]
    out["C9_MACD_gt_Signal"]  = out["MACD"] > out["MACD_Signal"]
    out["C10_RSI_gt_20"]      = out["RSI"] > 20

    out["Confirmations"] = out[CONFIRM_COLS].fillna(False).astype(int).sum(axis=1)

    conditions = [
        (out["Regime"] == "Bull") & (out["Confirmations"] >= 8),
        out["Regime"] == "Bear",
    ]
    out["Signal"] = np.select(conditions, ["LONG", "SHORT"], default="NEUTRAL")

    return out


def get_ticker_data(
    ticker:    str = "BTC-USD",
    period:    str = PERIOD,
    interval:  str = INTERVAL,
    n_states:  int = N_STATES,
    rand_seed: int = RANDOM_SEED,
) -> dict:
    """
    Full pipeline: download → features → indicators → HMM → signals.

    Returns dict with keys: df, bull_state_id, bear_state_id, state_summary, ticker
    """
    raw = download_ohlcv(ticker, period, interval)
    df  = engineer_features(raw)
    df  = add_indicators(df)
    df  = df.dropna(subset=_INDICATOR_COLS).copy()
    df, bull_id, bear_id, summary, _, _ = fit_hmm(df, n_states=n_states, random_state=rand_seed)
    df  = score_signals(df)

    return {
        "df":            df,
        "bull_state_id": bull_id,
        "bear_state_id": bear_id,
        "state_summary": summary,
        "ticker":        ticker,
    }
