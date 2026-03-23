"""
pipeline/features.py
────────────────────
Feature engineering for HMM training.

Computes Returns, Range, Vol_Change from OHLCV and applies IQR-based
outlier clipping to prevent degenerate HMM covariance matrices.

Public API
──────────
  engineer_features(df) → pd.DataFrame
  robust_clip(series, mult) → pd.Series
  FEATURE_COLS — ["Returns", "Range", "Vol_Change"]
"""

import numpy  as np
import pandas as pd

FEATURE_COLS = ["Returns", "Range", "Vol_Change"]


def robust_clip(series: pd.Series, mult: float) -> pd.Series:
    """Clip to [Q25 - mult×IQR, Q75 + mult×IQR]. Scale-invariant outlier removal."""
    q25, q75 = series.quantile(0.25), series.quantile(0.75)
    iqr = q75 - q25
    if iqr == 0:
        return series
    return series.clip(q25 - mult * iqr, q75 + mult * iqr)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Returns, Range, Vol_Change from OHLCV.
    Drops NaN/inf rows and applies IQR clipping.
    """
    out = df.copy()
    out["Returns"]    = out["Close"].pct_change()
    out["Range"]      = (out["High"] - out["Low"]) / out["Close"]
    out["Vol_Change"] = out["Volume"].pct_change()

    out = out.dropna(subset=FEATURE_COLS)
    out[FEATURE_COLS] = out[FEATURE_COLS].replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=FEATURE_COLS)

    out["Returns"]    = robust_clip(out["Returns"],    mult=10.0)
    out["Range"]      = robust_clip(out["Range"],      mult=10.0)
    out["Vol_Change"] = robust_clip(out["Vol_Change"], mult=5.0)

    return out
