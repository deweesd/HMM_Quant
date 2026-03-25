"""Unit tests for strategy/explain.py"""
import numpy as np
import pandas as pd
import pytest
from strategy.explain import get_scenario, get_historical_replay
from strategy.exits   import RECOMMENDED_LADDER, TRAILING_STOP_PCT
from strategy.backtest import LEVERAGE


def _minimal_df(n=300, entry_price=50000.0, signal_bar=None):
    """Minimal DataFrame with all columns needed by explain.py."""
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    signals = ["NEUTRAL"] * n
    if signal_bar is not None:
        signals[signal_bar] = "LONG"
    return pd.DataFrame({
        "Close":          [entry_price] * n,
        "Regime":         ["Bull"] * n,
        "Signal":         signals,
        "Confirmations":  [9] * n,
        "HMM_Confidence": [0.82] * n,
    }, index=dates)


# ── get_scenario ──────────────────────────────────────────────────────────────

def test_get_scenario_returns_all_required_keys():
    df     = _minimal_df()
    result = get_scenario(df, "BTC-USD", 1000.0, RECOMMENDED_LADDER)
    required = [
        "entry_price", "regime", "hmm_confidence", "regime_bars",
        "confirmations", "signal", "exit_schedule",
        "trailing_stop_price", "trailing_stop_loss",
        "avg_trade_duration_h", "risk_reward_ratio",
    ]
    for key in required:
        assert key in result, f"missing key: {key}"


def test_get_scenario_exit_schedule_count_matches_ladder():
    df     = _minimal_df()
    result = get_scenario(df, "BTC-USD", 1000.0, RECOMMENDED_LADDER)
    assert len(result["exit_schedule"]) == len(RECOMMENDED_LADDER)


def test_get_scenario_trigger_prices():
    df     = _minimal_df(entry_price=100.0)
    result = get_scenario(df, "TEST", 1000.0, RECOMMENDED_LADDER)
    for tier_result, tier_def in zip(result["exit_schedule"], RECOMMENDED_LADDER):
        expected = 100.0 * (1.0 + tier_def["gain_pct"] / 100.0)
        assert abs(tier_result["trigger_price"] - expected) < 0.01


def test_get_scenario_usd_remaining_decreases_through_schedule():
    df     = _minimal_df()
    result = get_scenario(df, "TEST", 1000.0, RECOMMENDED_LADDER)
    remainders = [t["usd_remaining"] for t in result["exit_schedule"]]
    for i in range(1, len(remainders)):
        assert remainders[i] < remainders[i - 1]


def test_get_scenario_trailing_stop_price():
    df     = _minimal_df(entry_price=50000.0)
    result = get_scenario(df, "TEST", 1000.0, RECOMMENDED_LADDER)
    expected = 50000.0 * (1.0 - TRAILING_STOP_PCT)
    assert abs(result["trailing_stop_price"] - expected) < 0.01


def test_get_scenario_trailing_stop_loss_is_negative():
    df     = _minimal_df()
    result = get_scenario(df, "TEST", 1000.0, RECOMMENDED_LADDER)
    assert result["trailing_stop_loss"] < 0.0


def test_get_scenario_risk_reward_ratio():
    df     = _minimal_df(entry_price=100.0)
    result = get_scenario(df, "TEST", 1000.0, RECOMMENDED_LADDER)
    # ratio = (1000 × 0.45 × 1.5) / abs(-1000 × 0.05 × 1.5) = 675 / 75 = 9.0
    assert abs(result["risk_reward_ratio"] - 9.0) < 0.01


def test_get_scenario_regime_bars_counts_correctly():
    # Last 50 bars are all Bull → regime_bars should be 50
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame({
        "Close":          [50000.0] * n,
        "Regime":         ["Neutral"] * 150 + ["Bull"] * 50,
        "Signal":         ["NEUTRAL"] * n,
        "Confirmations":  [9] * n,
        "HMM_Confidence": [0.8] * n,
    }, index=dates)
    result = get_scenario(df, "TEST", 1000.0, RECOMMENDED_LADDER)
    assert result["regime_bars"] == 50


# ── get_historical_replay ─────────────────────────────────────────────────────

def _df_with_trade():
    """df that produces exactly one completed LONG trade (Bear exit)."""
    n = 200
    dates   = pd.date_range("2024-01-01", periods=n, freq="h")
    closes  = [50000.0] * n
    regimes = ["Bull"] * 100 + ["Bear"] + ["Neutral"] * 99
    signals = ["LONG"] + ["NEUTRAL"] * 199
    return pd.DataFrame({
        "Close":          closes,
        "Regime":         regimes,
        "Signal":         signals,
        "Confirmations":  [9] * n,
        "HMM_Confidence": [0.85] * n,
    }, index=dates)


def test_get_historical_replay_structure():
    df     = _df_with_trade()
    result = get_historical_replay(df, n=5)
    if len(result) > 0:
        required = [
            "trade_num", "entry_time", "entry_price", "exit_time",
            "exit_price", "total_return_pct", "pnl_usd", "exit_reason",
            "duration_h", "confirmations_entry", "regime_at_entry",
            "partials_fired", "peak_gain_pct",
        ]
        for key in required:
            assert key in result[0], f"missing key: {key}"


def test_get_historical_replay_respects_n():
    df     = _df_with_trade()
    result = get_historical_replay(df, n=1)
    assert len(result) <= 1


def test_get_historical_replay_partials_fired_is_list():
    df     = _df_with_trade()
    result = get_historical_replay(df, n=5)
    if len(result) > 0:
        assert isinstance(result[0]["partials_fired"], list)


def test_get_historical_replay_no_trades_returns_empty():
    # No LONG signals → no trades
    n = 50
    df = pd.DataFrame({
        "Close":         [50000.0] * n,
        "Regime":        ["Bull"] * n,
        "Signal":        ["NEUTRAL"] * n,
        "Confirmations": [9] * n,
    }, index=pd.date_range("2024-01-01", periods=n, freq="h"))
    result = get_historical_replay(df, n=5)
    assert result == []
