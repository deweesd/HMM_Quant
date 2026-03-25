"""
strategy/explain.py
───────────────────
Explainability engine: forward-looking scenario calculator + historical replay.
Pure functions — no Streamlit imports, no side effects.

Caching of these functions is the caller's responsibility (handled in app/dashboard.py).

Public API
──────────
  get_scenario(df, ticker, position_usd, exit_thresholds) → dict
  get_historical_replay(df, n) → list[dict]
"""

import pandas as pd

from strategy.backtest import run_backtest, INITIAL_CAPITAL, LEVERAGE
from strategy.exits    import TRAILING_STOP_PCT


def get_scenario(
    df:              pd.DataFrame,
    ticker:          str,
    position_usd:    float,
    exit_thresholds: list,
) -> dict:
    """
    Forward-looking scenario calculator.

    Uses the most recent bar as the entry reference point.
    Calls run_backtest internally (recommended mode) for avg_trade_duration_h.

    Parameters
    ──────────
    df              — output of get_ticker_data()['df'] (must have Close, Regime,
                      Signal, Confirmations, HMM_Confidence)
    ticker          — string ticker label for display
    position_usd    — intended position size in USD
    exit_thresholds — ladder from build_exit_thresholds()
    """
    latest = df.iloc[-1]

    entry_price    = float(latest["Close"])
    regime         = str(latest.get("Regime", "Unknown"))
    signal         = str(latest.get("Signal", "NEUTRAL"))
    confirmations  = int(latest.get("Confirmations", 0))
    hmm_confidence = float(latest["HMM_Confidence"]) if "HMM_Confidence" in df.columns else 0.0

    # Consecutive bars in current regime (counting from end of df)
    regimes     = df["Regime"].values
    regime_bars = 1
    for j in range(len(regimes) - 2, -1, -1):
        if regimes[j] == regimes[-1]:
            regime_bars += 1
        else:
            break

    # Build exit schedule — iterate ladder directly (NOT via check_partial_exits)
    # One tier per iteration step; no same-bar multi-fire scenario in this calculator.
    exit_schedule = []
    position_frac = 1.0
    for idx, tier in enumerate(exit_thresholds):
        tgain   = tier["gain_pct"]
        is_last = (idx == len(exit_thresholds) - 1)

        resolved      = 0.50 * position_frac if is_last else tier["sell_fraction"]
        trigger_price = entry_price * (1.0 + tgain / 100.0)
        usd_realised  = position_usd * resolved
        position_frac -= resolved

        usd_remaining = position_usd * position_frac

        exit_schedule.append({
            "label":         f"Partial +{tgain}%",
            "trigger_price": round(trigger_price, 4),
            "usd_realised":  round(usd_realised, 2),
            "usd_remaining": round(usd_remaining, 2),
        })

    trailing_stop_price = entry_price * (1.0 - TRAILING_STOP_PCT)
    trailing_stop_loss  = -(position_usd * TRAILING_STOP_PCT * LEVERAGE)
    risk_reward_ratio   = (position_usd * 0.45 * LEVERAGE) / abs(trailing_stop_loss)

    avg_duration = _get_avg_duration(df)

    return {
        "entry_price":          round(entry_price, 4),
        "regime":               regime,
        "hmm_confidence":       round(hmm_confidence, 4),
        "regime_bars":          regime_bars,
        "confirmations":        confirmations,
        "signal":               signal,
        "exit_schedule":        exit_schedule,
        "trailing_stop_price":  round(trailing_stop_price, 4),
        "trailing_stop_loss":   round(trailing_stop_loss, 2),
        "avg_trade_duration_h": round(avg_duration, 1),
        "risk_reward_ratio":    round(risk_reward_ratio, 2),
    }


def _get_avg_duration(df: pd.DataFrame) -> float:
    """Mean Duration (h) of full-close trades from a recommended-mode backtest."""
    try:
        _, _, trades_df, _ = run_backtest(
            df, initial_capital=INITIAL_CAPITAL, leverage=LEVERAGE,
            position_mode="recommended",
        )
        if len(trades_df) == 0:
            return 0.0
        closed = trades_df[trades_df["Is Partial"] == False]
        return float(closed["Duration (h)"].mean()) if len(closed) > 0 else 0.0
    except Exception:
        return 0.0


def get_historical_replay(df: pd.DataFrame, n: int = 5) -> list:
    """
    Return the last n completed LONG trades, aggregated across partial exits.

    Calls run_backtest(df, INITIAL_CAPITAL, LEVERAGE, "recommended") internally.
    Caching is the caller's responsibility — do NOT add @st.cache_data here.

    Returns list[dict]. Each dict aggregates all trade rows that share an Entry Time.
    """
    _, _, trades_df, _ = run_backtest(
        df, initial_capital=INITIAL_CAPITAL, leverage=LEVERAGE,
        position_mode="recommended",
    )

    if len(trades_df) == 0:
        return []

    result = []
    for entry_time, group in trades_df.groupby("Entry Time", sort=False):
        full_close = group[group["Is Partial"] == False]
        if full_close.empty:
            continue

        close_row   = full_close.iloc[0]
        pnl_usd     = float(group["PnL ($)"].sum())
        eq_at_entry = float(close_row["Equity at Entry"])
        total_ret   = (pnl_usd / eq_at_entry * 100.0) if eq_at_entry != 0 else 0.0

        partials       = group[group["Is Partial"] == True]
        partials_fired = partials["Exit Reason"].tolist()

        peak_gain = (
            (float(close_row["Peak Price"]) / float(close_row["Entry Price"]) - 1.0)
            * LEVERAGE * 100.0
        )

        result.append({
            "trade_num":           len(result) + 1,
            "entry_time":          str(entry_time),
            "entry_price":         float(close_row["Entry Price"]),
            "exit_time":           str(close_row["Exit Time"]),
            "exit_price":          float(close_row["Exit Price"]),
            "total_return_pct":    round(total_ret, 2),
            "pnl_usd":             round(pnl_usd, 2),
            "exit_reason":         str(close_row["Exit Reason"]),
            "duration_h":          int(close_row["Duration (h)"]),
            "confirmations_entry": int(close_row["Confirmations at Entry"]),
            "regime_at_entry":     str(close_row["Regime at Entry"]),
            "partials_fired":      partials_fired,
            "peak_gain_pct":       round(peak_gain, 2),
        })

    return result[-n:] if len(result) > n else result
