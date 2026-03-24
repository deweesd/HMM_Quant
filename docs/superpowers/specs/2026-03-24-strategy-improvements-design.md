# Strategy Improvements — Design Spec
**Date:** 2026-03-24
**Status:** Approved
**Scope:** `strategy/exits.py` (new), `strategy/explain.py` (new), `strategy/backtest.py` (modified), `models/hmm.py` (modified), `app/dashboard.py` (modified — panels only, not visual redesign)

---

## 1. Goals

- Replace the single Bear-regime exit with a multi-tier profit-taking ladder plus a trailing stop
- Give users a clear, transparent view of when and why the strategy exits
- Add a forward-looking scenario calculator so users can project P&L before committing capital
- Add a historical signal replay so users can verify the track record
- Filter HMM regime noise with a minimum duration check to reduce false signals
- Surface all model parameters and strategy rules clearly in the About tab and on relevant chart elements

---

## 2. Architecture

```
strategy/exits.py      ← NEW  — trailing stop + partial exit ladder (pure functions)
strategy/explain.py    ← NEW  — scenario calculator + historical replay (pure functions)
strategy/backtest.py   ← MOD  — uses exits.py, richer trade log, position sizing params
models/hmm.py          ← MOD  — minimum regime duration filter on Regime column
app/dashboard.py       ← MOD  — scenario panel, historical replay panel, position toggle
```

All new modules are pure functions with no Streamlit imports and no side effects. The pipeline upstream of `strategy/` is unchanged.

---

## 3. `strategy/exits.py` — Exit Logic Module

### 3.1 Constants

```python
TRAILING_STOP_PCT  = 0.05   # exit if price drops 5% below peak since entry
MIN_REGIME_BARS    = 3      # defined in models/hmm.py, referenced here for clarity

RECOMMENDED_LADDER = [
    {"gain_pct": 15,  "sell_fraction": 0.10},
    {"gain_pct": 30,  "sell_fraction": 0.15},
    {"gain_pct": 45,  "sell_fraction": 0.20},
    {"gain_pct": 60,  "sell_fraction": 0.30},
    {"gain_pct": 100, "sell_fraction": 0.50},  # 50% of *remaining* position
]
```

After the +100% tier fires, the remaining position is held until Bear regime flip or trailing stop — no further partial exits.

### 3.2 `check_trailing_stop(current_price, peak_price, stop_pct) → bool`

Returns `True` if `current_price <= peak_price * (1 - stop_pct)`.

Stateless. The caller (backtest loop) is responsible for tracking `peak_price`.

### 3.3 `check_partial_exits(gain_pct, position_fraction, thresholds, tiers_fired) → list[dict]`

- `gain_pct` — current unrealised gain from entry as a percentage
- `position_fraction` — fraction of original position still held (0.0–1.0)
- `thresholds` — the full exit ladder (list of dicts with `gain_pct`, `sell_fraction`)
- `tiers_fired` — `set` of `gain_pct` values that have already triggered; the function skips these

Returns a list of exit actions that should fire at the current bar — each action is a dict:
```python
{"gain_pct": 30, "resolved_fraction": 0.15, "label": "Partial +30%"}
```

`resolved_fraction` is always expressed as a **fraction of the original position** (not of the remaining position). For all non-remainder tiers, `sell_fraction` from the ladder is a fraction of the **original** position — a tier with `sell_fraction=0.10` always closes exactly 10% of the original position when it fires, regardless of what prior partial exits have occurred. The caller reduces `position_fraction` by each `resolved_fraction` uniformly.

**Remainder tier identification:** The tier with the highest `gain_pct` in the ladder is the "remainder tier". For all other tiers, `resolved_fraction = sell_fraction` from the ladder dict. For the remainder tier only, `resolved_fraction = 0.50 × position_fraction_at_remainder`, where `position_fraction_at_remainder = position_fraction - sum(resolved_fraction for all lower tiers that also fire in this same call)`. This prevents the total resolved fraction from exceeding `position_fraction`.

Multiple thresholds can fire on the same bar if price jumps a tier in one move. The function iterates tiers in ascending `gain_pct` order and accumulates a running `sold_this_call` total (starting at 0.0). For each non-remainder tier that fires: `resolved_fraction = sell_fraction` from the dict; `sold_this_call += resolved_fraction`. When the remainder tier fires: `resolved_fraction = 0.50 × (position_fraction - sold_this_call)`. All `resolved_fraction` values are computed before the function returns — the caller reduces `position_fraction` by the sum of all returned `resolved_fraction` values after the call.

### 3.4 `build_exit_thresholds(mode, user_ladder) → list[dict]`

- `mode`: `"recommended"` or `"user_defined"`
- `user_ladder`: list of dicts provided by user when `mode == "user_defined"`

Returns the appropriate ladder. Validates user ladder:
- `gain_pct` values must be strictly ascending
- `sell_fraction` values for all tiers **except the last** (the remainder tier) must sum **< 1.0** (strictly less than); equal to 1.0 is rejected because nothing would remain for the remainder tier to sell
- The `sell_fraction` value on the remainder tier (last entry) is **ignored at runtime** — `resolved_fraction` for the remainder tier is always `0.50 × position_fraction_at_remainder` regardless of what value is in the dict. The validation does not check the remainder tier's `sell_fraction` value.
- Raises `ValueError` with a descriptive message on any validation failure

**Edge case in `check_partial_exits`:** If `position_fraction == 0.0` when the remainder tier would fire, the remainder tier is silently skipped (resolved_fraction = 0.0 and no action returned) rather than raising an error. This can only happen if a user-defined ladder passes validation with non-remainder fractions summing exactly to 1.0 — which is prevented by the `< 1.0` rule above. For the recommended ladder, this edge case cannot occur.

---

## 4. `strategy/backtest.py` — Modified

### 4.1 New signature

```python
def run_backtest(
    df:               pd.DataFrame,
    initial_capital:  float = INITIAL_CAPITAL,
    leverage:         float = LEVERAGE,
    position_mode:    str   = "recommended",   # "recommended" | "user_defined"
    user_exit_ladder: list  = None,            # only used when mode == "user_defined"
) -> tuple:
```

### 4.2 New state variables in the bar loop

```python
peak_price        = 0.0     # highest close since entry
position_fraction = 1.0     # fraction of original position still open
tiers_fired       = set()   # which gain_pct thresholds have already triggered
equity_at_entry   = 0.0     # equity value recorded when this position was opened
entry_bar         = -1      # bar index when position was opened; used to compute duration_bars
```

### 4.3 Updated bar loop priority order

**Equity accounting with partial exits:**
- `equity_at_entry` — recorded once when the position opens; never modified during the trade
- `equity` — the running total; starts at `initial_capital` and compounds across trades
- On a partial exit: `equity += equity_at_entry * resolved_fraction * (exit_price / entry_price - 1) * leverage`
- Mark-to-market (step 1): `equity_mtm = equity + equity_at_entry * position_fraction * leverage * (current_price / entry_price - 1)` — uses only the remaining fraction as the unrealised position base

For each bar:
1. **Mark-to-market** — record `equity_curve[i] = equity_mtm` (formula above). Recorded every bar regardless of what fires below. The existing mark-to-market line in `backtest.py` (`equity_values[i] = equity + unrealised`) must be replaced with this formula; the old formula uses `equity` as the position base, but the new formula uses `equity_at_entry * position_fraction` to correctly account for partially-closed positions. On a bar where a partial exit fires (step 5), the equity_curve entry recorded here reflects the mark-to-market *before* partial exit proceeds are realised; proceeds update `equity` and appear in the equity curve from bar i+1 onward. This one-bar lag on partial exit bars is intentional.
2. Update `peak_price = max(peak_price, current_price)` if in position
3. **Bear regime exit** — if in position and `Regime == "Bear"`: update `equity += equity_at_entry * position_fraction * (current_price / entry_price - 1) * leverage`, log final trade row with `Exit Reason: "Bear Regime"`, reset all position state (see below), then **`continue` to the next bar** (steps 4 and 5 are skipped for this bar)
4. **Trailing stop** — only evaluated if still in position after step 3; if `check_trailing_stop(price, peak_price)`: update `equity += equity_at_entry * position_fraction * (current_price / entry_price - 1) * leverage`, log final trade row with `Exit Reason: "Trailing Stop"`, reset all position state (see below), then **`continue` to the next bar** (step 5 is skipped for this bar)
5. **Partial exits** — only evaluated if still in position after steps 3 and 4; call `check_partial_exits(gain_pct, position_fraction, thresholds, tiers_fired)`, then for each returned action: add its `gain_pct` to `tiers_fired`, reduce `position_fraction` by `resolved_fraction`, update `equity += equity_at_entry * resolved_fraction * (current_price / entry_price - 1) * leverage`, log as a separate trade row
6. **Entry** — open position if `signal == "LONG"` and cooldown elapsed and not in position; when opening, record `equity_at_entry = equity` (current equity before this entry) and `entry_bar = i`

**Position state reset (steps 3 and 4):** Set `in_position = False`, `entry_price = 0.0`, `peak_price = 0.0`, `position_fraction = 1.0`, `tiers_fired = set()`, `equity_at_entry = 0.0`, `entry_bar = -1`, `last_exit_bar = i`.

**End-of-data force-close:** After the bar loop, if still in position, force-close the remaining position with `Exit Reason: "End of Data"`. At this point `peak_price` still holds the correct peak from the last bar (step 2 ran on the final bar), so pass `peak_price` directly to `_make_trade`. Duration is `len(df) - 1 - entry_bar`.

### 4.4 Richer trade log columns

Every row in `trades_df` (partial or full close) includes:

| Column | Description |
|---|---|
| `Entry Time` | Bar timestamp when position was opened |
| `Exit Time` | Bar timestamp of this partial/full close |
| `Entry Price` | Price at position open |
| `Exit Price` | Price at this exit |
| `Return %` | `(exit_price / entry_price - 1) * leverage * 100` — per-unit price return for this exit, independent of `resolved_fraction` |
| `PnL ($)` | USD profit/loss for the fraction closed on this row: `equity_at_entry * resolved_fraction * (exit_price / entry_price - 1) * leverage` |
| `Position %` | `resolved_fraction * 100` — fraction of original position closed on this row (e.g. 10.0) |
| `Is Partial` | `True` for partial exit rows; `False` for full-close rows (Bear Regime, Trailing Stop, End of Data) |
| `Equity at Entry` | Value of `equity` at the time the position was opened; same for all rows of the same trade |
| `Peak Price` | Highest price reached since entry at time of exit |
| `Regime at Entry` | Bull/Bear/Neutral at entry bar |
| `Confirmations at Entry` | Integer 0–10 at entry bar |
| `Duration (h)` | Bars from entry to this exit |
| `Exit Reason` | "Partial +15%", "Partial +30%", ..., "Bear Regime", "Trailing Stop", "End of Data" |

### 4.5 `_make_trade()` — replacement helper

The existing `_make_trade()` helper must be **replaced** with a new version that accepts all columns in the new schema. New signature:

```python
def _make_trade(
    entry_time, exit_time,
    entry_price, exit_price,
    resolved_fraction,
    equity_at_entry,
    leverage,
    peak_price,
    regime_at_entry,
    confirmations_at_entry,
    duration_bars: int,
    exit_reason,
) -> dict:
```

`duration_bars` is the integer number of bars from entry to this exit (bars are 1-hour cadence, so `duration_bars == Duration (h)`).

Returns a dict with all 14 columns from Section 4.4. `Is Partial` is `True` when `exit_reason.startswith("Partial")`, otherwise `False`.

`_empty_trades_df()` must return a DataFrame with the 14 columns listed in Section 4.4 as its schema (empty, correct dtypes).

### 4.6 `_compute_metrics()` — partial-exit awareness

`_compute_metrics()` continues to derive total return, max drawdown, and Sharpe from the equity curve (unchanged). For trade-level statistics, it must filter to non-partial rows only:

- **Win Rate** — computed on rows where `Is Partial == False` (one row per completed trade)
- **Avg Trade Return** — computed on rows where `Is Partial == False`
- **Total Trades** — count of rows where `Is Partial == False`

The full unfiltered `trades_df` (containing both partial and full-close rows) is passed to `_compute_metrics`. The function applies `trades[trades["Is Partial"] == False]` before computing win rate, avg trade return, and total trades. Win rate is `(Return % > 0).mean()` on the filtered rows, where `Return %` is the per-unit price return for the full-close row.

Partial rows are included in the equity curve computation and the trade log display, but excluded from the per-trade aggregate statistics above.

The section formerly numbered 4.5 ("Metrics unchanged") is superseded by this section.

---

## 5. `models/hmm.py` — Minimum Regime Duration Filter

### 5.1 New constant

```python
MIN_REGIME_BARS = 3   # regime must persist ≥ 3 consecutive bars to be confirmed
```

### 5.2 Filter logic

After `df_out["Regime"]` is assigned, apply a post-processing smoothing pass to produce the final `Regime` column. The algorithm operates on the **original predicted sequence** (a copy taken before modification), not on the partially-smoothed output, to prevent one reversion from cascading into adjacent runs:

```
raw = df_out["Regime"].copy()         # original HMM-predicted labels
smoothed = raw.copy()

i = 0
while i < len(raw):
    if i == 0:
        prev_label = raw[0]           # bar-0 edge case: no prior bar; prev_label = first label
        i += 1
        continue
    if raw[i] != prev_label:
        # measure run length of new regime in the *original* sequence
        j = i
        while j < len(raw) and raw[j] == raw[i]:
            j += 1
        run_length = j - i
        if run_length < MIN_REGIME_BARS:
            smoothed[i:j] = prev_label    # revert short run to previous regime
        else:
            prev_label = raw[i]           # new regime confirmed; update prev
        i = j
    else:
        prev_label = raw[i]
        i += 1

df_out["Regime"] = smoothed

# Note: after bar 0, the outer loop always advances `i` to `j` (first bar of a new,
# different regime), so raw[i] != prev_label is always true on loop re-entry for i≥1.
# The `else` branch (raw[i] == prev_label) never executes after bar 0.
# It is retained only as a structural guard — do not add logic to it.
```

`HMM_State` (the raw integer state) is **not** modified — smoothing only affects the `Regime` string label.

**Bar-0 policy:** Bar 0 is always retained in the smoothed output regardless of its run length, because there is no prior regime context to revert it to. This is intentional — `prev_label` is initialised to `raw[0]` and the filter only reverts runs with a confirmed predecessor.

**Final-bar behaviour:** If the DataFrame ends mid-run (i.e., the most recent bars form a run shorter than `MIN_REGIME_BARS`), those bars are reverted to the previous confirmed regime. Callers that use the most recent bar's `Regime` for live signal generation must be aware that the "current" regime label may show a prior regime even if the raw HMM output has already transitioned. This is intentional — the filter requires confirmation before acting on a regime change.

### 5.3 `fit_hmm()` return value — no breaking changes

The function signature and return tuple are unchanged. The posterior probability matrix (`model.predict_proba(X_scaled)`) is computed internally. The row-wise maximum posterior probability is stored as `df_out["HMM_Confidence"]` (float, 0.0–1.0) directly on the returned dataframe.

All callers that need confidence values read them from `df["HMM_Confidence"]` on the dataframe returned by `fit_hmm()`. `HMM_Confidence` is **not** added to the return tuple.

**Import dependency chain:** `exits.py` has no internal project imports. `backtest.py` imports from `exits.py` only. `explain.py` imports from `backtest.py` and `exits.py`. There are no circular dependencies.

**Pipeline ordering:** The smoothing filter in `fit_hmm()` is applied before the dataframe is returned. The `Confirmations` column is computed by `strategy/signals.py` downstream, reading the already-smoothed `Regime` column from the returned dataframe. No changes to `strategy/signals.py` are required.

**Parameter naming:** `build_exit_thresholds` uses parameter `mode`; `run_backtest` uses parameter `position_mode`. These are separate functions with separate parameters — do not confuse them.

**`HMM_Confidence` and smoothing:** For bars where smoothing has reverted the `Regime` label, `HMM_Confidence` retains the raw model's posterior probability for the original (unsmoothed) predicted state. No adjustment is made for smoothing — the column always reflects raw HMM output.

---

## 6. `strategy/explain.py` — Explainability Engine

### 6.1 `get_scenario(df, ticker, position_usd, exit_thresholds) → dict`

Forward-looking calculator. Uses the most recent LONG signal bar as the reference entry point.

**Inputs:**
- `df` — output of `get_ticker_data()`
- `ticker` — string, used for display labels
- `position_usd` — float, user's intended position size in USD
- `exit_thresholds` — ladder from `build_exit_thresholds()`

The function calls `run_backtest(df, initial_capital=INITIAL_CAPITAL, leverage=LEVERAGE, position_mode="recommended")` internally to derive `avg_trade_duration_h` (mean of `Duration (h)` on `Is Partial == False` rows). Caching of this call is the caller's responsibility — `app/dashboard.py` wraps the `get_scenario` call in a `@st.cache_data`-decorated function.

**Output dict:**
```python
{
    "entry_price":       float,          # current/latest close
    "regime":            str,            # current regime label
    "hmm_confidence":    float,          # HMM_Confidence at latest bar (0–1)
    "regime_bars":       int,            # consecutive bars in current regime
    "confirmations":     int,            # current confirmation count
    "signal":            str,            # LONG / NEUTRAL / SHORT
    "exit_schedule": [                   # one row per ladder tier
        {
            "label":         "Partial +15%",
            "trigger_price": float,      # entry_price * (1 + gain_pct / 100)
            "usd_realised":  float,      # position_usd * resolved_fraction (using resolved_fraction as defined in Section 3.3, i.e. fraction of original position)
            "usd_remaining": float,      # position_usd minus cumulative sum of usd_realised through and including this tier
        },
        ...
    ],
    # Note: get_scenario does NOT call check_partial_exits. It iterates the ladder directly:
    # for each non-remainder tier: resolved_fraction = sell_fraction (fraction of original)
    # for the remainder tier (last): resolved_fraction = 0.50 × current position_fraction
    # position_fraction is decremented by resolved_fraction after each tier.
    # usd_realised = position_usd * resolved_fraction
    # usd_remaining = position_usd * (position_fraction after decrement)
    "trailing_stop_price": float,        # entry_price * 0.95
    "trailing_stop_loss":  float,        # USD loss if stop fires immediately at entry; stored as a negative float (e.g., -50.0 = $50 loss)
    "avg_trade_duration_h": float,       # mean bars-in-position from historical trades
    "risk_reward_ratio":   float,        # (position_usd * 0.45 * leverage) / abs(trailing_stop_loss)
                                         # numerator: hypothetical gain on full position at +45% (standardised reference, always 0.45 regardless of exit_thresholds)
                                         # denominator: trailing_stop_loss from this dict
}
```

### 6.2 `get_historical_replay(df, n=5) → list[dict]`

Returns the last `n` completed LONG trades from the backtest trade log enriched with context.

**Each entry:**
```python
{
    "trade_num":           int,
    "entry_time":          str,          # formatted datetime
    "entry_price":         float,
    "exit_time":           str,
    "exit_price":          float,
    "total_return_pct":    float,        # full trade return %
    "pnl_usd":             float,        # USD P&L for full trade
    "exit_reason":         str,
    "duration_h":          int,
    "confirmations_entry": int,
    "regime_at_entry":     str,
    "partials_fired":      list[str],    # e.g. ["Partial +15%", "Partial +30%"]
    "peak_gain_pct":       float,        # max unrealised gain during trade; computed as (Peak Price / Entry Price - 1) * leverage * 100 from the trade's final-close row
}
```

`get_historical_replay()` is a plain function in `strategy/explain.py` with no Streamlit imports or decorators. It calls `run_backtest(df, initial_capital=INITIAL_CAPITAL, leverage=LEVERAGE, position_mode="recommended")` using constants imported from `strategy/backtest.py`. In `app/dashboard.py`, the call is wrapped in a `@st.cache_data`-decorated function — the caching decorator does not live in `explain.py`.

**Note on `total_return_pct`:** This reflects the blended return across all partial and final closes and will differ from the final-close row's `Return %` when partial exits fired at different prices. The dashboard must use `total_return_pct` from this aggregated dict, not `Return %` from any individual trade log row.

**Aggregating across partial exits:** All rows for a logical trade share the same `Entry Time`. For each group:
- `pnl_usd` = sum of `PnL ($)` across all rows in the group (partial + final close)
- `total_return_pct` = `pnl_usd / equity_at_entry * 100` (return on equity committed); `equity_at_entry` is read from any row in the group (all rows carry the same value)
- `partials_fired` = list of `Exit Reason` from rows where `Is Partial == True`, sorted chronologically
- `exit_reason` = `Exit Reason` from the final-close row (`Is Partial == False`)
- `duration_h` = `Duration (h)` from the final-close row
- `confirmations_entry`, `regime_at_entry` = from any row in the group (all rows share these values)

---

## 7. Dashboard Changes (`app/dashboard.py`)

### 7.1 Scenario Calculator panel (Live tab)

Placed directly below the Hero Signal Banner, above the ticker cards. Only shown when `signal == "LONG"`.

**Controls (in sidebar):**
- Position mode toggle: `st.radio("Position Mode", ["Recommended", "User Defined"])`
- Position size: `st.number_input("Position Size (USD)", min_value=100, value=1000)`
- If User Defined: collapsible section with 5 threshold inputs (gain %, sell fraction)

**Panel output:**
- Entry price, regime, confidence, bars-in-regime, confirmation count
- Exit schedule table: Tier | Trigger Price | USD Realised | USD Remaining
- Trailing stop price and max USD loss
- Risk/reward ratio

### 7.2 Historical Signal Replay (Backtest tab)

Placed above the equity chart. Shows last 5 completed LONG trades as compact cards:
- Entry → Exit date range, duration
- Total return % and USD P&L (green/red coloured)
- Partial exits that fired (badge pills)
- Regime and confirmation count at entry

### 7.3 About tab additions

New section: **"How the Strategy Protects Your Position"** explaining in plain language:
- The 5-tier exit ladder with the de-risking logic ("by +60%, 75% of your position is already secured")
- The trailing stop ("once you're profitable, a moving floor prevents giving back more than 5% from the peak")
- The 3-bar regime filter ("the model waits for 3 consecutive hours of the same regime before confirming a signal — this filters out single-candle noise")
- Bear regime exit ("when the HMM detects a Bear regime for 3+ consecutive bars, the remaining position closes immediately regardless of current gain")

New section: **"Understanding Bull, Bear, and Neutral Regimes"**:
- Plain-English definition of each regime
- What triggers a regime change
- Why Neutral is not a sell signal
- The difference between a regime label and a trade signal

All model parameters surfaced in the "Model Parameters" table:
- Add `MIN_REGIME_BARS`, `TRAILING_STOP_PCT`, and the full exit ladder

### 7.4 Chart annotation

The candlestick chart gains regime duration annotations: when hovering over a bar, the tooltip shows `Regime: Bull (14 bars)` alongside price data. No visual clutter added — tooltip only.

---

## 8. Out of Scope

- No changes to `pipeline/download.py`, `pipeline/features.py`, `pipeline/indicators.py`
- No changes to the visual redesign (covered in separate spec `2026-03-24-dashboard-redesign-design.md`)
- No live order execution or brokerage integration
- No user account persistence (position mode resets on page reload in this iteration)
- No backtesting of user-defined ladders against historical data (the scenario calculator uses Recommended ladder metrics for the risk/reward estimate regardless of mode)

---

## 9. Files Changed

| File | Action | Key change |
|---|---|---|
| `strategy/exits.py` | Create | Trailing stop + partial exit ladder logic |
| `strategy/explain.py` | Create | Scenario calculator + historical replay |
| `strategy/backtest.py` | Modify | Use exits.py, richer trade log, position mode params |
| `models/hmm.py` | Modify | MIN_REGIME_BARS filter, HMM_Confidence column |
| `app/dashboard.py` | Modify | Scenario panel, replay panel, position toggle, About copy |
| `tests/test_exits.py` | Create | Unit tests for all exits.py functions |
| `tests/test_explain.py` | Create | Unit tests for explain.py functions |
