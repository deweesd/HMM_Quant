"""
////// strategy/backtest.py \\\\\\
──────────────────────────────────────────────────────────────────────────────
Regime-based trading strategy simulation.

Strategy Rules
──────────────
  Starting capital : $20,000
  Leverage         : 1.5×  (applied to PnL calculation, not margin)
  Entry condition  : Signal == 'LONG'  (Bull regime + 8/10 confirmations)
  Exit condition   : Regime flips to 'Bear'  (hard stop)
  Cooldown         : 72 hours after ANY exit — no re-entry allowed
  Position sizing  : 100% of current equity per trade (no fractional sizing)

PnL Formula
───────────
  trade_return = (exit_price - entry_price) / entry_price × leverage
  new_equity   = old_equity × (1 + trade_return)

  The equity compounds across trades.  With 1.5× leverage a 2% price move
  produces a 3% equity move.  Losses are also amplified symmetrically.

Backtest Loop Logic
───────────────────
  The loop is intentionally sequential (not vectorised) because cooldown,
  leverage, and bear-exit rules create state dependencies between bars.

  For each bar i:
    1. Record mark-to-market equity (unrealised PnL if in position)
    2. Check Bear-exit   → close position, reset cooldown
    3. Check entry       → open position if signal + cooldown elapsed
    NOTE: exit and entry cannot both fire on the same bar because after
    a Bear-exit `in_position` is False, so the entry check is skipped
    (the regime is still 'Bear' at that bar).

Public API
──────────
  run_backtest(df, initial_capital, leverage) →
      (equity_curve, bh_curve, trades_df, metrics)
"""

import numpy  as np
import pandas as pd

# ── Strategy constants ─────────────────────────────────────────────────────────
INITIAL_CAPITAL = 20_000.0
LEVERAGE        = 1.5
COOLDOWN_BARS   = 72   # one hour per bar → 72-hour cooldown


# ══════════════════════════════════════════════════════════════════════════════
# MAIN BACKTEST FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def run_backtest(
    df:              pd.DataFrame,
    initial_capital: float = INITIAL_CAPITAL,
    leverage:        float = LEVERAGE,
) -> tuple:
    """
    Run the regime-based strategy on the prepared DataFrame.

    Parameters
    ──────────
    df               — output of data_prep.get_ticker_data()['df']
                       must contain: Close, Regime, Signal, Confirmations
    initial_capital  — starting cash in USD (default $20,000)
    leverage         — simulated leverage multiplier (default 1.5×)

    Returns
    ───────
    equity_curve : pd.Series  — portfolio value at every bar (index = datetime)
    bh_curve     : pd.Series  — buy-and-hold value at every bar
    trades_df    : pd.DataFrame — log of every completed trade
    metrics      : dict       — summary performance statistics
    """
    # ── Clean input ────────────────────────────────────────────────────────────
    df = df.dropna(subset=["Close", "Regime", "Signal"]).copy()
    df = df.sort_index()

    n = len(df)
    if n < 2:
        raise ValueError("DataFrame has fewer than 2 clean rows — cannot backtest.")

    closes  = df["Close"].values
    regimes = df["Regime"].values
    signals = df["Signal"].values
    index   = df.index

    # ── State variables ────────────────────────────────────────────────────────
    equity          = initial_capital
    in_position     = False
    entry_price     = 0.0
    entry_bar       = -1
    last_exit_bar   = -(COOLDOWN_BARS + 1)   # allow entry from bar 0

    equity_values   = np.empty(n)
    trades          = []

    # ══════════════════════════════════════════════════════════════════════════
    # BAR-BY-BAR LOOP
    # ══════════════════════════════════════════════════════════════════════════
    for i in range(n):
        price  = closes[i]
        regime = regimes[i]
        signal = signals[i]

        # ── 1. Mark-to-market equity ──────────────────────────────────────────
        if in_position:
            unrealised = equity * leverage * (price - entry_price) / entry_price
            equity_values[i] = equity + unrealised
        else:
            equity_values[i] = equity

        # ── 2. Bear-exit (highest priority — close immediately) ───────────────
        if in_position and regime == "Bear":
            trade_ret = leverage * (price - entry_price) / entry_price
            equity    = equity * (1.0 + trade_ret)

            trades.append(_make_trade(
                entry_bar   = entry_bar,
                exit_bar    = i,
                entry_time  = index[entry_bar],
                exit_time   = index[i],
                entry_price = entry_price,
                exit_price  = price,
                trade_ret   = trade_ret,
                equity      = equity,
                reason      = "Bear Regime",
            ))

            in_position   = False
            entry_price   = 0.0
            last_exit_bar = i
            # Update the mark-to-market to reflect realised equity
            equity_values[i] = equity
            continue

        # ── 3. Entry ──────────────────────────────────────────────────────────
        cooldown_ok = (i - last_exit_bar) >= COOLDOWN_BARS
        if not in_position and signal == "LONG" and cooldown_ok:
            in_position = True
            entry_price = price
            entry_bar   = i

    # ── Force-close any open position at end of data ──────────────────────────
    if in_position:
        last_price = closes[-1]
        trade_ret  = leverage * (last_price - entry_price) / entry_price
        equity     = equity * (1.0 + trade_ret)
        equity_values[-1] = equity

        trades.append(_make_trade(
            entry_bar   = entry_bar,
            exit_bar    = n - 1,
            entry_time  = index[entry_bar],
            exit_time   = index[-1],
            entry_price = entry_price,
            exit_price  = last_price,
            trade_ret   = trade_ret,
            equity      = equity,
            reason      = "End of Data",
        ))

    # ── Build outputs ──────────────────────────────────────────────────────────
    equity_curve = pd.Series(equity_values, index=index, name="Portfolio")
    bh_curve     = pd.Series(
        initial_capital * (closes / closes[0]),
        index = index,
        name  = "Buy & Hold",
    )
    trades_df = pd.DataFrame(trades) if trades else _empty_trades_df()
    metrics   = _compute_metrics(equity_curve, bh_curve, trades_df, initial_capital)

    return equity_curve, bh_curve, trades_df, metrics


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _make_trade(
    entry_bar, exit_bar, entry_time, exit_time,
    entry_price, exit_price, trade_ret, equity, reason,
) -> dict:
    """Package a single completed trade as a dict for the trade log."""
    pnl_usd   = equity - INITIAL_CAPITAL   # cumulative equity relative to start
    pnl_trade = trade_ret * 100            # this trade's % return
    duration  = exit_bar - entry_bar       # bars (hours)
    return {
        "Entry Time":   entry_time,
        "Exit Time":    exit_time,
        "Entry Price":  round(float(entry_price), 4),
        "Exit Price":   round(float(exit_price),  4),
        "Return %":     round(float(pnl_trade),   3),
        "Duration (h)": int(duration),
        "Exit Reason":  reason,
    }


def _empty_trades_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "Entry Time", "Exit Time", "Entry Price", "Exit Price",
        "Return %", "Duration (h)", "Exit Reason",
    ])


def _compute_metrics(
    equity_curve:    pd.Series,
    bh_curve:        pd.Series,
    trades:          pd.DataFrame,
    initial_capital: float,
) -> dict:
    """
    Compute summary performance metrics.

    Metrics
    ───────
    Total Return    — strategy equity growth from start to end (%)
    Buy & Hold      — passive hold return over same period (%)
    Alpha           — Total Return minus Buy & Hold (percentage points)
    Win Rate        — % of trades that were profitable
    Max Drawdown    — largest peak-to-trough decline in equity (%)
    Sharpe Ratio    — annualised Sharpe using hourly bars (8760 hrs/yr,
                      crypto trades 24/7 so we do NOT use 252 trading days)
    Total Trades    — number of completed round-trips
    Avg Trade Ret   — mean per-trade return (%)
    """
    final_equity = float(equity_curve.iloc[-1])
    total_return = (final_equity / initial_capital - 1.0) * 100.0

    bh_return = (float(bh_curve.iloc[-1]) / initial_capital - 1.0) * 100.0
    alpha     = total_return - bh_return

    # Max drawdown
    rolling_max  = equity_curve.cummax()
    drawdown_pct = ((equity_curve - rolling_max) / rolling_max) * 100.0
    max_drawdown = float(drawdown_pct.min())

    # Hourly Sharpe (annualised for 24/7 crypto: 365 × 24 = 8760 bars/yr)
    hourly_rets = equity_curve.pct_change().dropna()
    if hourly_rets.std() > 0:
        sharpe = float(hourly_rets.mean() / hourly_rets.std() * np.sqrt(8760))
    else:
        sharpe = 0.0

    # Trade stats
    n_trades = len(trades)
    if n_trades > 0:
        win_rate  = float((trades["Return %"] > 0).sum() / n_trades * 100)
        avg_trade = float(trades["Return %"].mean())
    else:
        win_rate  = 0.0
        avg_trade = 0.0

    return {
        "Total Return (%)":    round(total_return, 2),
        "Buy & Hold (%)":      round(bh_return,    2),
        "Alpha (pp)":          round(alpha,         2),
        "Win Rate (%)":        round(win_rate,      1),
        "Max Drawdown (%)":    round(max_drawdown,  2),
        "Sharpe Ratio":        round(sharpe,         2),
        "Total Trades":        n_trades,
        "Avg Trade Return (%)":round(avg_trade,      3),
        "Final Equity ($)":    round(final_equity,   2),
    }
