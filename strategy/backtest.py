"""
////// strategy/backtest.py \\\\\\
──────────────────────────────────────────────────────────────────────────────
Regime-based trading strategy simulation with partial exits.

Strategy Rules
──────────────
  Starting capital : $20,000
  Leverage         : 1.5×
  Entry condition  : Signal == 'LONG'  (Bull regime + 8/10 confirmations)
  Exit conditions  : (1) Regime flips to 'Bear'  (immediate full close)
                     (2) Trailing stop: price drops 5% below peak since entry
                     (3) Partial exits: multi-tier profit-taking ladder
  Cooldown         : 72 hours after ANY exit
  Position sizing  : 100% of current equity per trade

Equity Formula (partial-exit aware)
────────────────────────────────────
  equity_at_entry is recorded once at entry and never changed during the trade.
  On each partial or full exit:
    equity += equity_at_entry × resolved_fraction × (exit_price/entry_price − 1) × leverage
  Mark-to-market:
    equity_mtm = equity + equity_at_entry × position_fraction × leverage × (price/entry_price − 1)

Public API
──────────
  run_backtest(df, initial_capital, leverage, position_mode, user_exit_ladder) →
      (equity_curve, bh_curve, trades_df, metrics)
"""

import numpy  as np
import pandas as pd

from strategy.exits import (
    build_exit_thresholds,
    check_trailing_stop,
    check_partial_exits,
    TRAILING_STOP_PCT,
)

# ── Strategy constants ────────────────────────────────────────────────────────
INITIAL_CAPITAL = 20_000.0
LEVERAGE        = 1.5
COOLDOWN_BARS   = 72


# ══════════════════════════════════════════════════════════════════════════════
# MAIN BACKTEST FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def run_backtest(
    df:               pd.DataFrame,
    initial_capital:  float = INITIAL_CAPITAL,
    leverage:         float = LEVERAGE,
    position_mode:    str   = "recommended",   # "recommended" | "user_defined"
    user_exit_ladder: list  = None,
) -> tuple:
    """
    Run the regime-based strategy on the prepared DataFrame.

    Parameters
    ──────────
    df               — output of strategy.signals.get_ticker_data()['df']
                       must contain: Close, Regime, Signal, Confirmations
    initial_capital  — starting cash in USD (default $20,000)
    leverage         — simulated leverage multiplier (default 1.5×)
    position_mode    — "recommended" uses RECOMMENDED_LADDER;
                       "user_defined" uses user_exit_ladder
    user_exit_ladder — required when position_mode == "user_defined"

    Returns
    ───────
    equity_curve : pd.Series  — portfolio mark-to-market at every bar
    bh_curve     : pd.Series  — buy-and-hold value at every bar
    trades_df    : pd.DataFrame — every partial and full close (14 columns)
    metrics      : dict       — summary performance statistics
    """
    df = df.dropna(subset=["Close", "Regime", "Signal"]).copy()
    df = df.sort_index()

    n = len(df)
    if n < 2:
        raise ValueError("DataFrame has fewer than 2 clean rows — cannot backtest.")

    closes        = df["Close"].values
    regimes       = df["Regime"].values
    signals       = df["Signal"].values
    confirmations = (
        df["Confirmations"].values.astype(int)
        if "Confirmations" in df.columns
        else np.zeros(n, dtype=int)
    )
    index = df.index

    thresholds = build_exit_thresholds(position_mode, user_exit_ladder)

    # ── State variables ───────────────────────────────────────────────────────
    equity                 = initial_capital
    in_position            = False
    entry_price            = 0.0
    entry_bar              = -1
    last_exit_bar          = -(COOLDOWN_BARS + 1)
    peak_price             = 0.0
    position_fraction      = 1.0
    tiers_fired            = set()
    equity_at_entry        = 0.0
    regime_at_entry        = ""
    confirmations_at_entry = 0
    # Track index into trades list at entry so we can remove partials on trailing stop
    trade_start_idx        = 0

    equity_values = np.empty(n)
    trades        = []

    # ══════════════════════════════════════════════════════════════════════════
    # BAR-BY-BAR LOOP
    # ══════════════════════════════════════════════════════════════════════════
    for i in range(n):
        price  = closes[i]
        regime = regimes[i]
        signal = signals[i]

        # ── 1. Mark-to-market ─────────────────────────────────────────────────
        if in_position:
            unrealised = (
                equity_at_entry * position_fraction * leverage
                * (price - entry_price) / entry_price
            )
            equity_values[i] = equity + unrealised
        else:
            equity_values[i] = equity

        # ── 2. Update peak_price ──────────────────────────────────────────────
        if in_position:
            peak_price = max(peak_price, price)

        # ── 3. Bear regime exit ───────────────────────────────────────────────
        if in_position and regime == "Bear":
            pnl     = equity_at_entry * position_fraction * (price / entry_price - 1.0) * leverage
            equity += pnl
            equity_values[i] = equity

            trades.append(_make_trade(
                entry_time=index[entry_bar], exit_time=index[i],
                entry_price=entry_price, exit_price=price,
                resolved_fraction=position_fraction,
                equity_at_entry=equity_at_entry, leverage=leverage,
                peak_price=peak_price,
                regime_at_entry=regime_at_entry,
                confirmations_at_entry=confirmations_at_entry,
                duration_bars=i - entry_bar,
                exit_reason="Bear Regime",
            ))
            in_position = False;  entry_price = 0.0;  peak_price = 0.0
            position_fraction = 1.0;  tiers_fired = set();  equity_at_entry = 0.0
            entry_bar = -1;  last_exit_bar = i
            continue

        # ── 4. Trailing stop ──────────────────────────────────────────────────
        if in_position and check_trailing_stop(price, peak_price, TRAILING_STOP_PCT):
            # Remove any partial exit rows for this trade; close full original position
            del trades[trade_start_idx:]
            equity  = equity_at_entry
            pnl     = equity_at_entry * 1.0 * (price / entry_price - 1.0) * leverage
            equity += pnl
            equity_values[i] = equity

            trades.append(_make_trade(
                entry_time=index[entry_bar], exit_time=index[i],
                entry_price=entry_price, exit_price=price,
                resolved_fraction=1.0,
                equity_at_entry=equity_at_entry, leverage=leverage,
                peak_price=peak_price,
                regime_at_entry=regime_at_entry,
                confirmations_at_entry=confirmations_at_entry,
                duration_bars=i - entry_bar,
                exit_reason="Trailing Stop",
            ))
            in_position = False;  entry_price = 0.0;  peak_price = 0.0
            position_fraction = 1.0;  tiers_fired = set();  equity_at_entry = 0.0
            entry_bar = -1;  last_exit_bar = i
            continue

        # ── 5. Partial exits ──────────────────────────────────────────────────
        if in_position:
            gain_pct = round((price / entry_price - 1.0) * 100.0, 6)
            actions  = check_partial_exits(
                gain_pct, position_fraction, thresholds, tiers_fired
            )
            for action in actions:
                rf          = action["resolved_fraction"]
                pnl         = equity_at_entry * rf * (price / entry_price - 1.0) * leverage
                equity     += pnl
                position_fraction -= rf
                tiers_fired.add(action["gain_pct"])
                trades.append(_make_trade(
                    entry_time=index[entry_bar], exit_time=index[i],
                    entry_price=entry_price, exit_price=price,
                    resolved_fraction=rf,
                    equity_at_entry=equity_at_entry, leverage=leverage,
                    peak_price=peak_price,
                    regime_at_entry=regime_at_entry,
                    confirmations_at_entry=confirmations_at_entry,
                    duration_bars=i - entry_bar,
                    exit_reason=action["label"],
                ))

        # ── 6. Entry ──────────────────────────────────────────────────────────
        cooldown_ok = (i - last_exit_bar) >= COOLDOWN_BARS
        if not in_position and signal == "LONG" and cooldown_ok:
            in_position            = True
            entry_price            = price
            entry_bar              = i
            peak_price             = price
            equity_at_entry        = equity
            position_fraction      = 1.0
            tiers_fired            = set()
            regime_at_entry        = regime
            confirmations_at_entry = int(confirmations[i])
            trade_start_idx        = len(trades)

    # ── Force-close any open position at end of data ──────────────────────────
    if in_position:
        last_price  = closes[-1]
        pnl         = equity_at_entry * position_fraction * (last_price / entry_price - 1.0) * leverage
        equity     += pnl
        equity_values[-1] = equity

        trades.append(_make_trade(
            entry_time=index[entry_bar], exit_time=index[-1],
            entry_price=entry_price, exit_price=last_price,
            resolved_fraction=position_fraction,
            equity_at_entry=equity_at_entry, leverage=leverage,
            peak_price=peak_price,
            regime_at_entry=regime_at_entry,
            confirmations_at_entry=confirmations_at_entry,
            duration_bars=(n - 1) - entry_bar,
            exit_reason="End of Data",
        ))

    # ── Build outputs ─────────────────────────────────────────────────────────
    equity_curve = pd.Series(equity_values, index=index, name="Portfolio")
    bh_curve     = pd.Series(
        initial_capital * (closes / closes[0]),
        index=index, name="Buy & Hold",
    )
    trades_df = pd.DataFrame(trades) if trades else _empty_trades_df()
    if len(trades_df) > 0:
        trades_df["Is Partial"] = trades_df["Is Partial"].astype(object)
    metrics   = _compute_metrics(equity_curve, bh_curve, trades_df, initial_capital)

    return equity_curve, bh_curve, trades_df, metrics


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _make_trade(
    entry_time, exit_time,
    entry_price: float, exit_price: float,
    resolved_fraction: float,
    equity_at_entry: float,
    leverage: float,
    peak_price: float,
    regime_at_entry: str,
    confirmations_at_entry: int,
    duration_bars: int,
    exit_reason: str,
) -> dict:
    """Package a single trade exit (partial or full) as a dict for the trade log."""
    price_return = (exit_price / entry_price - 1.0)
    pnl_usd      = equity_at_entry * resolved_fraction * price_return * leverage
    return_pct   = price_return * leverage * 100.0
    is_partial   = bool(exit_reason.startswith("Partial"))
    return {
        "Entry Time":              entry_time,
        "Exit Time":               exit_time,
        "Entry Price":             round(float(entry_price), 4),
        "Exit Price":              round(float(exit_price), 4),
        "Return %":                round(float(return_pct), 3),
        "PnL ($)":                 round(float(pnl_usd), 2),
        "Position %":              round(float(resolved_fraction * 100), 2),
        "Is Partial":              is_partial,
        "Equity at Entry":         round(float(equity_at_entry), 2),
        "Peak Price":              round(float(peak_price), 4),
        "Regime at Entry":         regime_at_entry,
        "Confirmations at Entry":  int(confirmations_at_entry),
        "Duration (h)":            int(duration_bars),
        "Exit Reason":             exit_reason,
    }


def _empty_trades_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "Entry Time", "Exit Time", "Entry Price", "Exit Price",
        "Return %", "PnL ($)", "Position %", "Is Partial", "Equity at Entry",
        "Peak Price", "Regime at Entry", "Confirmations at Entry",
        "Duration (h)", "Exit Reason",
    ])


def _compute_metrics(
    equity_curve:    pd.Series,
    bh_curve:        pd.Series,
    trades:          pd.DataFrame,
    initial_capital: float,
) -> dict:
    """
    Compute summary performance metrics.

    Win Rate, Total Trades, and Avg Trade Return are computed on full-close rows only
    (Is Partial == False). Equity-curve metrics (Total Return, Drawdown, Sharpe) use
    the full curve which already reflects partial exit proceeds.
    """
    final_equity = float(equity_curve.iloc[-1])
    total_return = (final_equity / initial_capital - 1.0) * 100.0
    bh_return    = (float(bh_curve.iloc[-1]) / initial_capital - 1.0) * 100.0
    alpha        = total_return - bh_return

    rolling_max  = equity_curve.cummax()
    drawdown_pct = ((equity_curve - rolling_max) / rolling_max) * 100.0
    max_drawdown = float(drawdown_pct.min())

    hourly_rets = equity_curve.pct_change().dropna()
    sharpe = (
        float(hourly_rets.mean() / hourly_rets.std() * np.sqrt(8760))
        if hourly_rets.std() > 0 else 0.0
    )

    # Filter to full-close rows for per-trade statistics
    if len(trades) > 0 and "Is Partial" in trades.columns:
        closed = trades[trades["Is Partial"] == False]
    else:
        closed = trades

    n_trades = len(closed)
    if n_trades > 0:
        win_rate  = float((closed["Return %"] > 0).sum() / n_trades * 100)
        avg_trade = float(closed["Return %"].mean())
    else:
        win_rate  = 0.0
        avg_trade = 0.0

    return {
        "Total Return (%)":     round(total_return, 2),
        "Buy & Hold (%)":       round(bh_return,    2),
        "Alpha (pp)":           round(alpha,         2),
        "Win Rate (%)":         round(win_rate,      1),
        "Max Drawdown (%)":     round(max_drawdown,  2),
        "Sharpe Ratio":         round(sharpe,         2),
        "Total Trades":         n_trades,
        "Avg Trade Return (%)": round(avg_trade,      3),
        "Final Equity ($)":     round(final_equity,   2),
    }
