"""
pipeline/download.py
────────────────────
Download hourly OHLCV data from yfinance.

Public API
──────────
  download_ohlcv(ticker, period, interval) → pd.DataFrame
  TICKERS        — list of 4 ticker strings
  TICKER_LABELS  — {ticker: short_name}
  REQUIRED_COLS  — column names expected from yfinance
  PERIOD         — default data window ("730d")
  INTERVAL       — default bar interval ("1h")
"""

import pandas as pd
import yfinance as yf

TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD"]
TICKER_LABELS = {
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
    "SOL-USD": "SOL",
    "ADA-USD": "ADA",
}
PERIOD   = "730d"
INTERVAL = "1h"
REQUIRED_COLS = ["Open", "High", "Low", "Close", "Volume"]


def download_ohlcv(ticker: str, period: str = PERIOD, interval: str = INTERVAL) -> pd.DataFrame:
    """
    Download OHLCV from yfinance and return a flat DataFrame with exactly
    Open / High / Low / Close / Volume columns.
    """
    raw = yf.download(
        ticker,
        period      = period,
        interval    = interval,
        auto_adjust = True,
        progress    = False,
        prepost     = False,
    )

    if raw.empty:
        raise ValueError(
            f"yfinance returned no data for {ticker}. "
            "Check internet connection or try a smaller period."
        )

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw = raw.loc[:, ~raw.columns.duplicated()]

    missing = [c for c in REQUIRED_COLS if c not in raw.columns]
    if missing:
        raise KeyError(
            f"{ticker}: columns {missing} missing after MultiIndex flatten. "
            f"Available: {raw.columns.tolist()}"
        )

    return raw[REQUIRED_COLS].dropna(how="all").sort_index()
