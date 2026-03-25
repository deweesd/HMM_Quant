import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy  as np


def _make_df(n=50):
    idx   = pd.date_range("2025-01-01", periods=n, freq="h")
    close = np.random.uniform(95, 105, n)
    df    = pd.DataFrame({
        "Open":   close * np.random.uniform(0.995, 1.005, n),
        "High":   close * np.random.uniform(1.005, 1.015, n),
        "Low":    close * np.random.uniform(0.985, 0.995, n),
        "Close":  close,
        "Volume": np.random.randint(1000, 5000, n),
        "EMA20":  close * np.random.uniform(0.99, 1.01, n),
        "EMA200": close * np.random.uniform(0.97, 1.03, n),
        "Regime": np.random.choice(["Bull", "Bear", "Neutral"], n),
    }, index=idx)
    return df


def test_candlestick_transparent_background():
    """build_candlestick must use transparent chart backgrounds."""
    from app.dashboard import build_candlestick
    fig = build_candlestick(_make_df(), "BTC-USD")
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)", \
        f"Expected transparent paper_bgcolor, got {fig.layout.paper_bgcolor}"
    assert fig.layout.plot_bgcolor  == "rgba(0,0,0,0)", \
        f"Expected transparent plot_bgcolor, got {fig.layout.plot_bgcolor}"


def test_equity_chart_transparent_background():
    """build_equity_chart must use transparent chart backgrounds."""
    from app.dashboard import build_equity_chart
    idx    = pd.date_range("2025-01-01", periods=50, freq="h")
    equity = pd.Series(np.linspace(20000, 28000, 50), index=idx)
    bh     = pd.Series(np.linspace(20000, 24000, 50), index=idx)
    fig    = build_equity_chart(equity, bh, "BTC-USD")
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.plot_bgcolor  == "rgba(0,0,0,0)"
