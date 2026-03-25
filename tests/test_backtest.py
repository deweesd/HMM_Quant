"""Integration tests for the updated strategy/backtest.py"""
import numpy as np
import pandas as pd
import pytest
from strategy.backtest import run_backtest, INITIAL_CAPITAL, LEVERAGE, _make_trade


# ── Fixture helpers ───────────────────────────────────────────────────────────

def _make_df(closes, regimes, signals, confirmations=None, freq="h"):
    """Build a minimal DataFrame for backtest tests."""
    n = len(closes)
    dates = pd.date_range("2024-01-01", periods=n, freq=freq)
    return pd.DataFrame({
        "Close":         closes,
        "Regime":        regimes,
        "Signal":        signals,
        "Confirmations": confirmations if confirmations is not None else [9] * n,
    }, index=dates)


# ── _make_trade ───────────────────────────────────────────────────────────────

def test_make_trade_columns():
    row = _make_trade(
        entry_time=pd.Timestamp("2024-01-01"),
        exit_time=pd.Timestamp("2024-01-02"),
        entry_price=50000.0,
        exit_price=55000.0,
        resolved_fraction=1.0,
        equity_at_entry=20000.0,
        leverage=1.5,
        peak_price=55000.0,
        regime_at_entry="Bull",
        confirmations_at_entry=9,
        duration_bars=24,
        exit_reason="Bear Regime",
    )
    expected_cols = [
        "Entry Time", "Exit Time", "Entry Price", "Exit Price",
        "Return %", "PnL ($)", "Position %", "Is Partial", "Equity at Entry",
        "Peak Price", "Regime at Entry", "Confirmations at Entry",
        "Duration (h)", "Exit Reason",
    ]
    for col in expected_cols:
        assert col in row, f"missing column: {col}"


def test_make_trade_is_partial_false_for_bear():
    row = _make_trade(
        entry_time=pd.Timestamp("2024-01-01"),
        exit_time=pd.Timestamp("2024-01-02"),
        entry_price=50000.0, exit_price=55000.0,
        resolved_fraction=1.0, equity_at_entry=20000.0, leverage=1.5,
        peak_price=55000.0, regime_at_entry="Bull",
        confirmations_at_entry=9, duration_bars=24, exit_reason="Bear Regime",
    )
    assert row["Is Partial"] is False


def test_make_trade_is_partial_true_for_partial():
    row = _make_trade(
        entry_time=pd.Timestamp("2024-01-01"),
        exit_time=pd.Timestamp("2024-01-02"),
        entry_price=50000.0, exit_price=57500.0,
        resolved_fraction=0.10, equity_at_entry=20000.0, leverage=1.5,
        peak_price=57500.0, regime_at_entry="Bull",
        confirmations_at_entry=9, duration_bars=10, exit_reason="Partial +15%",
    )
    assert row["Is Partial"] is True


def test_make_trade_pnl_formula():
    # entry=50000, exit=55000 → 10% price return × leverage 1.5 = 15% return
    # pnl = 20000 × 1.0 × 0.10 × 1.5 = 3000.0
    row = _make_trade(
        entry_time=pd.Timestamp("2024-01-01"),
        exit_time=pd.Timestamp("2024-01-02"),
        entry_price=50000.0, exit_price=55000.0,
        resolved_fraction=1.0, equity_at_entry=20000.0, leverage=1.5,
        peak_price=55000.0, regime_at_entry="Bull",
        confirmations_at_entry=9, duration_bars=24, exit_reason="Bear Regime",
    )
    assert abs(row["PnL ($)"] - 3000.0) < 0.01
    assert abs(row["Return %"] - 15.0) < 0.001


# ── bar loop: bear exit ───────────────────────────────────────────────────────

def test_bear_exit_produces_single_trade():
    # Bar 0: LONG signal, Bull regime (entry)
    # Bars 1-10: Bull (held)
    # Bar 11: Bear (exit)
    n = 12
    closes  = [50000.0] * 10 + [55000.0] + [55000.0]
    regimes = ["Bull"] * 11 + ["Bear"]
    signals = ["LONG"] + ["NEUTRAL"] * 11
    df = _make_df(closes, regimes, signals)

    eq, bh, trades, metrics = run_backtest(df, initial_capital=20000.0, leverage=1.5)

    assert len(trades) == 1
    assert trades.iloc[0]["Exit Reason"] == "Bear Regime"
    assert trades.iloc[0]["Is Partial"] is False


def test_bear_exit_equity_update():
    # Entry at 50000, exit at 55000, position_fraction=1.0, leverage=1.5
    # PnL = 20000 × 1.0 × (55000/50000 - 1) × 1.5 = 20000 × 0.10 × 1.5 = 3000
    # Final equity = 23000
    n = 5
    closes  = [50000.0, 50000.0, 50000.0, 55000.0, 55000.0]
    regimes = ["Bull", "Bull", "Bull", "Bull", "Bear"]
    signals = ["LONG", "NEUTRAL", "NEUTRAL", "NEUTRAL", "NEUTRAL"]
    df = _make_df(closes, regimes, signals)

    eq, bh, trades, metrics = run_backtest(df, initial_capital=20000.0, leverage=1.5)

    assert abs(trades.iloc[0]["PnL ($)"] - 3000.0) < 0.01
    assert abs(metrics["Final Equity ($)"] - 23000.0) < 0.01


# ── bar loop: trailing stop ───────────────────────────────────────────────────

def test_trailing_stop_fires_before_bear():
    # Entry at 50000, price rises to 60000 (peak), then drops to 57000 (5% below 60000)
    # 60000 × 0.95 = 57000 → stop fires before any Bear regime
    closes  = [50000.0, 55000.0, 60000.0, 57000.0]
    regimes = ["Bull", "Bull", "Bull", "Bull"]
    signals = ["LONG", "NEUTRAL", "NEUTRAL", "NEUTRAL"]
    df = _make_df(closes, regimes, signals)

    eq, bh, trades, metrics = run_backtest(df, initial_capital=20000.0, leverage=1.5)

    assert len(trades) == 1
    assert trades.iloc[0]["Exit Reason"] == "Trailing Stop"


# ── bar loop: partial exits ───────────────────────────────────────────────────

def test_partial_exit_produces_separate_row():
    # Entry at 50000, price rises to 57500 (+15%) at bar 2 → partial +15% fires
    # Then Bear exit at bar 3
    closes  = [50000.0, 50000.0, 57500.0, 57500.0]
    regimes = ["Bull", "Bull", "Bull", "Bear"]
    signals = ["LONG", "NEUTRAL", "NEUTRAL", "NEUTRAL"]
    df = _make_df(closes, regimes, signals)

    eq, bh, trades, metrics = run_backtest(df, initial_capital=20000.0, leverage=1.5)

    # One partial row + one full-close row
    assert len(trades) == 2
    reasons = set(trades["Exit Reason"])
    assert "Partial +15%" in reasons
    assert "Bear Regime" in reasons


def test_partial_rows_excluded_from_win_rate():
    # Same setup as above: 1 win (bear exit at profit), 1 partial row
    closes  = [50000.0, 50000.0, 57500.0, 57500.0]
    regimes = ["Bull", "Bull", "Bull", "Bear"]
    signals = ["LONG", "NEUTRAL", "NEUTRAL", "NEUTRAL"]
    df = _make_df(closes, regimes, signals)

    eq, bh, trades, metrics = run_backtest(df)

    # Win rate based on 1 full-close trade (profitable) → 100%
    assert metrics["Win Rate (%)"] == 100.0
    assert metrics["Total Trades"] == 1


def test_position_fraction_reduces_after_partial():
    # Entry at 50000, price 57500 (+15%) → partial fires, then price stays flat
    # Then Bear exit at bar 4 — position_fraction should be 0.90 at Bear exit
    closes  = [50000.0, 50000.0, 57500.0, 57500.0, 57500.0]
    regimes = ["Bull", "Bull", "Bull", "Bull", "Bear"]
    signals = ["LONG", "NEUTRAL", "NEUTRAL", "NEUTRAL", "NEUTRAL"]
    df = _make_df(closes, regimes, signals)

    eq, bh, trades, metrics = run_backtest(df, initial_capital=20000.0, leverage=1.5)

    bear_row = trades[trades["Exit Reason"] == "Bear Regime"].iloc[0]
    # Position % for the Bear exit row = remaining fraction × 100 = 90.0
    assert abs(bear_row["Position %"] - 90.0) < 0.01


# ── _compute_metrics ──────────────────────────────────────────────────────────

def test_compute_metrics_keys():
    n = 5
    closes  = [50000.0] * 5
    regimes = ["Bull"] * 5
    signals = ["NEUTRAL"] * 5
    df = _make_df(closes, regimes, signals)
    eq, bh, trades, metrics = run_backtest(df)

    required = [
        "Total Return (%)", "Buy & Hold (%)", "Alpha (pp)", "Win Rate (%)",
        "Max Drawdown (%)", "Sharpe Ratio", "Total Trades",
        "Avg Trade Return (%)", "Final Equity ($)",
    ]
    for k in required:
        assert k in metrics
