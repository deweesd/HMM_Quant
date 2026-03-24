# Strategy Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-tier profit-taking exit ladder, trailing stop, minimum regime duration filter, and an explainability layer (scenario calculator + historical replay) to the HMM trading strategy.

**Architecture:** Pure-function modules `strategy/exits.py` and `strategy/explain.py` are created first with no side effects; `strategy/backtest.py` and `models/hmm.py` are surgically updated to use them; `app/dashboard.py` gets three new UI panels wired to the new modules.

**Tech Stack:** Python 3.9, pandas, numpy, hmmlearn, Streamlit, pytest

**Spec:** `docs/superpowers/specs/2026-03-24-strategy-improvements-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `strategy/exits.py` | Create | `check_trailing_stop`, `check_partial_exits`, `build_exit_thresholds` |
| `strategy/explain.py` | Create | `get_scenario`, `get_historical_replay` |
| `strategy/backtest.py` | Modify | New signature, partial-exit bar loop, `_make_trade`, `_compute_metrics` |
| `models/hmm.py` | Modify | Smoothing pass on `Regime`, `HMM_Confidence` column |
| `app/dashboard.py` | Modify | Sidebar controls, Scenario panel, Replay panel, README sections |
| `tests/test_exits.py` | Create | Unit tests for all `exits.py` functions |
| `tests/test_explain.py` | Create | Unit tests for `explain.py` functions |
| `tests/test_backtest.py` | Create | Integration tests for the updated bar loop |
| `tests/test_hmm_smoothing.py` | Create | Unit tests for the regime smoothing helper |

Import dependency chain (no cycles): `exits.py` → (no project imports) · `backtest.py` → `exits.py` · `explain.py` → `backtest.py`, `exits.py`

---

## Task 1: strategy/exits.py

**Files:**
- Create: `strategy/exits.py`
- Create: `tests/test_exits.py`

---

- [ ] **Step 1.1: Write failing tests**

Create `tests/test_exits.py`:

```python
"""Unit tests for strategy/exits.py"""
import pytest
from strategy.exits import (
    check_trailing_stop,
    check_partial_exits,
    build_exit_thresholds,
    RECOMMENDED_LADDER,
    TRAILING_STOP_PCT,
)

# ── check_trailing_stop ───────────────────────────────────────────────────────

def test_trailing_stop_fires_at_threshold():
    # peak=100, 5% below = 95.0 exactly → fires
    assert check_trailing_stop(95.0, 100.0, 0.05) is True

def test_trailing_stop_fires_below_threshold():
    assert check_trailing_stop(90.0, 100.0, 0.05) is True

def test_trailing_stop_does_not_fire_above_threshold():
    assert check_trailing_stop(95.01, 100.0, 0.05) is False

def test_trailing_stop_does_not_fire_at_peak():
    assert check_trailing_stop(100.0, 100.0, 0.05) is False


# ── check_partial_exits ───────────────────────────────────────────────────────

_LADDER_3 = [
    {"gain_pct": 15, "sell_fraction": 0.10},   # non-remainder
    {"gain_pct": 30, "sell_fraction": 0.15},   # non-remainder
    {"gain_pct": 50, "sell_fraction": 0.50},   # remainder tier
]

def test_partial_exits_non_remainder_uses_sell_fraction():
    actions = check_partial_exits(
        gain_pct=20.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    assert len(actions) == 1
    assert actions[0]["gain_pct"] == 15
    assert abs(actions[0]["resolved_fraction"] - 0.10) < 1e-9

def test_partial_exits_skips_fired_tier():
    # +15% already fired; gain=20 → only +30% not yet reached, nothing fires
    actions = check_partial_exits(
        gain_pct=20.0, position_fraction=0.90,
        thresholds=_LADDER_3, tiers_fired={15}
    )
    assert len(actions) == 0

def test_partial_exits_no_action_below_threshold():
    actions = check_partial_exits(
        gain_pct=10.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    assert len(actions) == 0

def test_partial_exits_multiple_tiers_fire_same_bar():
    # gain=35 → +15% and +30% both fire (neither is the remainder at 50%)
    actions = check_partial_exits(
        gain_pct=35.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    fired = {a["gain_pct"] for a in actions}
    assert 15 in fired and 30 in fired

def test_partial_exits_remainder_accounts_for_sold_this_call():
    # All 3 tiers fire: sold_this_call = 0.10 + 0.15 = 0.25
    # remainder resolved = 0.50 × (1.0 - 0.25) = 0.375
    actions = check_partial_exits(
        gain_pct=60.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    remainder = next(a for a in actions if a["gain_pct"] == 50)
    assert abs(remainder["resolved_fraction"] - 0.375) < 1e-9

def test_partial_exits_remainder_uses_current_position_fraction():
    # position_fraction=0.75 (prior partials fired earlier), remainder fires alone
    actions = check_partial_exits(
        gain_pct=60.0, position_fraction=0.75,
        thresholds=_LADDER_3, tiers_fired={15, 30}
    )
    assert len(actions) == 1
    assert actions[0]["gain_pct"] == 50
    # sold_this_call=0 (no non-remainder fires), resolved = 0.50 × 0.75
    assert abs(actions[0]["resolved_fraction"] - 0.375) < 1e-9

def test_partial_exits_label_format():
    actions = check_partial_exits(
        gain_pct=20.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    assert actions[0]["label"] == "Partial +15%"

def test_recommended_ladder_has_5_tiers():
    assert len(RECOMMENDED_LADDER) == 5

def test_recommended_ladder_gain_pcts():
    gains = [t["gain_pct"] for t in RECOMMENDED_LADDER]
    assert gains == [15, 30, 45, 60, 100]


# ── build_exit_thresholds ─────────────────────────────────────────────────────

def test_build_returns_recommended_ladder():
    result = build_exit_thresholds("recommended")
    assert result is RECOMMENDED_LADDER

def test_build_user_defined_valid():
    ladder = [
        {"gain_pct": 20, "sell_fraction": 0.10},
        {"gain_pct": 50, "sell_fraction": 0.20},
        {"gain_pct": 80, "sell_fraction": 0.50},
    ]
    assert build_exit_thresholds("user_defined", ladder) == ladder

def test_build_user_defined_not_ascending_raises():
    ladder = [
        {"gain_pct": 50, "sell_fraction": 0.10},
        {"gain_pct": 20, "sell_fraction": 0.20},
        {"gain_pct": 80, "sell_fraction": 0.50},
    ]
    with pytest.raises(ValueError, match="strictly ascending"):
        build_exit_thresholds("user_defined", ladder)

def test_build_user_defined_fractions_too_high_raises():
    # non-remainder sum = 0.60 + 0.40 = 1.0 → rejected (must be < 1.0)
    ladder = [
        {"gain_pct": 20, "sell_fraction": 0.60},
        {"gain_pct": 50, "sell_fraction": 0.40},
        {"gain_pct": 80, "sell_fraction": 0.50},
    ]
    with pytest.raises(ValueError):
        build_exit_thresholds("user_defined", ladder)

def test_build_invalid_mode_raises():
    with pytest.raises(ValueError):
        build_exit_thresholds("unknown_mode")

def test_build_user_defined_empty_raises():
    with pytest.raises(ValueError):
        build_exit_thresholds("user_defined", [])
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /Users/dmd/Desktop/HMM_Quant/HMM_Quant
.venv/bin/pytest tests/test_exits.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError: No module named 'strategy.exits'`

- [ ] **Step 1.3: Create strategy/exits.py**

```python
"""
strategy/exits.py
─────────────────
Exit logic: trailing stop + partial exit ladder (pure functions, no side effects).

Public API
──────────
  TRAILING_STOP_PCT   — 0.05 (exit if price falls 5% below peak)
  RECOMMENDED_LADDER  — 5-tier profit-taking schedule
  check_trailing_stop(current_price, peak_price, stop_pct) → bool
  check_partial_exits(gain_pct, position_fraction, thresholds, tiers_fired) → list[dict]
  build_exit_thresholds(mode, user_ladder) → list[dict]
"""

TRAILING_STOP_PCT = 0.05   # exit if price drops 5% below peak since entry
MIN_REGIME_BARS   = 3      # defined in models/hmm.py; referenced here for clarity

RECOMMENDED_LADDER = [
    {"gain_pct": 15,  "sell_fraction": 0.10},
    {"gain_pct": 30,  "sell_fraction": 0.15},
    {"gain_pct": 45,  "sell_fraction": 0.20},
    {"gain_pct": 60,  "sell_fraction": 0.30},
    {"gain_pct": 100, "sell_fraction": 0.50},  # remainder tier — sell_fraction ignored at runtime
]


def check_trailing_stop(current_price: float, peak_price: float, stop_pct: float) -> bool:
    """Return True if price has fallen stop_pct or more below peak_price."""
    return current_price <= peak_price * (1.0 - stop_pct)


def check_partial_exits(
    gain_pct: float,
    position_fraction: float,
    thresholds: list,
    tiers_fired: set,
) -> list:
    """
    Return exit actions for tiers that fire at the current bar.

    Parameters
    ──────────
    gain_pct          — current unrealised gain from entry (%)
    position_fraction — fraction of original position still held (0.0–1.0)
    thresholds        — full exit ladder (list of dicts with gain_pct, sell_fraction)
    tiers_fired       — set of gain_pct values already triggered; skipped

    Returns
    ───────
    list[dict] with keys: gain_pct, resolved_fraction, label
    resolved_fraction is a fraction of the ORIGINAL position.
    For non-remainder tiers: resolved_fraction = sell_fraction from dict.
    For remainder tier (highest gain_pct): resolved_fraction =
      0.50 × (position_fraction - sum of non-remainder resolved_fractions
      that also fire in this same call).
    """
    sorted_tiers   = sorted(thresholds, key=lambda t: t["gain_pct"])
    max_gain_pct   = sorted_tiers[-1]["gain_pct"] if sorted_tiers else None
    actions        = []
    sold_this_call = 0.0

    for tier in sorted_tiers:
        tgain = tier["gain_pct"]
        if tgain in tiers_fired:
            continue
        if gain_pct < tgain:
            continue

        if tgain == max_gain_pct:
            resolved = 0.50 * (position_fraction - sold_this_call)
        else:
            resolved        = tier["sell_fraction"]
            sold_this_call += resolved

        actions.append({
            "gain_pct":          tgain,
            "resolved_fraction": resolved,
            "label":             f"Partial +{tgain}%",
        })

    return actions


def build_exit_thresholds(mode: str, user_ladder: list = None) -> list:
    """
    Return exit ladder for the given mode.

    Raises ValueError on bad mode or invalid user_ladder.
    Validation: gain_pct strictly ascending; non-remainder sell_fraction sum < 1.0.
    The last tier's (remainder) sell_fraction is ignored at runtime.
    """
    if mode == "recommended":
        return RECOMMENDED_LADDER

    if mode != "user_defined":
        raise ValueError(f"mode must be 'recommended' or 'user_defined', got {mode!r}")

    if not user_ladder:
        raise ValueError("user_ladder must be a non-empty list when mode='user_defined'")

    gain_pcts = [t["gain_pct"] for t in user_ladder]
    for i in range(1, len(gain_pcts)):
        if gain_pcts[i] <= gain_pcts[i - 1]:
            raise ValueError(
                f"user_ladder gain_pct values must be strictly ascending; "
                f"found {gain_pcts[i - 1]} followed by {gain_pcts[i]}"
            )

    non_remainder_sum = sum(t["sell_fraction"] for t in user_ladder[:-1])
    if non_remainder_sum >= 1.0:
        raise ValueError(
            f"user_ladder non-remainder sell_fraction values sum to "
            f"{non_remainder_sum:.4f} — must be strictly less than 1.0"
        )

    return user_ladder
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_exits.py -v
```
Expected: all tests PASS

- [ ] **Step 1.5: Commit**

```bash
git add strategy/exits.py tests/test_exits.py
git commit -m "feat: add strategy/exits.py — trailing stop + partial exit ladder"
```

---

## Task 2: models/hmm.py — smoothing filter + HMM_Confidence

**Files:**
- Modify: `models/hmm.py:23-94`
- Create: `tests/test_hmm_smoothing.py`

---

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_hmm_smoothing.py`:

```python
"""Tests for the regime smoothing helper in models/hmm.py"""
import numpy as np
from models.hmm import _smooth_regimes, MIN_REGIME_BARS


def test_short_run_reverted():
    # B B N N B B B — NN is length 2 < MIN_REGIME_BARS=3 → reverted to B
    raw = np.array(["B", "B", "N", "N", "B", "B", "B"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["B", "B", "B", "B", "B", "B", "B"]


def test_long_run_kept():
    # B B N N N B B — NNN is length 3 >= 3 → kept
    raw = np.array(["B", "B", "N", "N", "N", "B", "B"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["B", "B", "N", "N", "N", "B", "B"]


def test_bar_0_always_retained():
    # Even if bar 0 starts a 1-bar run, it is kept (no prior context)
    raw = np.array(["N", "B", "B", "B", "B"])
    result = _smooth_regimes(raw, 3)
    # The N at bar 0 has no prior, so it is kept.
    # "B" run starting at bar 1 is length 4 >= 3 → confirmed.
    assert result[0] == "N"
    assert list(result[1:]) == ["B", "B", "B", "B"]


def test_final_short_run_reverted():
    # B B B N N — NN at the end is length 2 < 3 → reverted to B
    raw = np.array(["B", "B", "B", "N", "N"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["B", "B", "B", "B", "B"]


def test_cascading_prevented():
    # Operating on raw sequence prevents cascade:
    # B B N N B B B N N B B B
    # NN (pos 2-3): length 2 < 3 → reverted to B
    # BBB (pos 4-6): confirmed
    # NN (pos 7-8): length 2 < 3 → reverted to B (prev is B, from confirmed BBB)
    raw = np.array(["B","B","N","N","B","B","B","N","N","B","B","B"])
    result = _smooth_regimes(raw, 3)
    # All N runs reverted to B
    assert all(r == "B" for r in result)


def test_single_bar_sequence():
    raw = np.array(["Bull"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["Bull"]


def test_min_regime_bars_constant_is_3():
    assert MIN_REGIME_BARS == 3
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_hmm_smoothing.py -v 2>&1 | head -20
```
Expected: `ImportError: cannot import name '_smooth_regimes'`

- [ ] **Step 2.3: Update models/hmm.py**

Add `MIN_REGIME_BARS = 3` after `RANDOM_SEED`. Add the `_smooth_regimes` helper. Call it inside `fit_hmm`. Add `HMM_Confidence`.

Replace the entire file with:

```python
"""
models/hmm.py
─────────────
Fit GaussianHMM on engineered features and label Bull/Bear/Neutral regimes.

Public API
──────────
  fit_hmm(df, n_states, random_state) →
      (df_out, bull_state_id, bear_state_id, state_summary, model, scaler)
  N_STATES       — default number of HMM hidden states (6)
  RANDOM_SEED    — default random seed (42)
  MIN_REGIME_BARS — minimum consecutive bars before a regime change is confirmed (3)
"""

import warnings
import numpy  as np
import pandas as pd
from hmmlearn.hmm          import GaussianHMM
from sklearn.preprocessing import StandardScaler

from pipeline.features import FEATURE_COLS

N_STATES     = 6
RANDOM_SEED  = 42
MIN_REGIME_BARS = 3   # regime must persist ≥ 3 consecutive bars to be confirmed


def _smooth_regimes(raw: np.ndarray, min_bars: int) -> np.ndarray:
    """
    Apply minimum-duration filter to a regime label array.

    Operates on the original predicted sequence (no cascade): short runs (< min_bars)
    are reverted to the previous confirmed regime. Bar 0 is always retained.

    After the loop, i always lands on the first bar of a new (different) regime;
    the else branch (same label) is dead code for all bars after bar 0 and must
    not be given additional logic.
    """
    if len(raw) == 0:
        return raw.copy()

    smoothed   = raw.copy()
    n          = len(raw)
    prev_label = raw[0]
    i          = 1

    while i < n:
        if raw[i] != prev_label:
            # Measure run length of new regime in the *original* sequence
            j = i
            while j < n and raw[j] == raw[i]:
                j += 1
            run_length = j - i
            if run_length < min_bars:
                smoothed[i:j] = prev_label  # revert short run
            else:
                prev_label = raw[i]         # new regime confirmed
            i = j
        else:
            # Dead code after bar 0: i always lands on a new-regime bar after any run
            prev_label = raw[i]
            i += 1

    return smoothed


def fit_hmm(df: pd.DataFrame, n_states: int = N_STATES, random_state: int = RANDOM_SEED):
    """
    Fit a GaussianHMM on the three scaled features.

    Returns
    ───────
    df_out        — input df with 'HMM_State', 'Regime', 'HMM_Confidence' columns added
    bull_state_id — int, state with highest mean return
    bear_state_id — int, state with lowest mean return
    state_summary — pd.DataFrame with one row per state
    model         — fitted GaussianHMM
    scaler        — fitted StandardScaler

    Notes
    ─────
    'Regime' is smoothed: short runs (< MIN_REGIME_BARS) are reverted to the prior
    confirmed regime. 'HMM_State' retains raw model output. 'HMM_Confidence' is the
    row-wise max posterior probability from model.predict_proba — it is NOT adjusted
    for smoothing and always reflects the raw model output.

    Callers read HMM_Confidence from df["HMM_Confidence"]; it is NOT in the return tuple.
    """
    X_raw    = df[FEATURE_COLS].values
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    model = GaussianHMM(
        n_components    = n_states,
        covariance_type = "full",
        n_iter          = 1000,
        random_state    = random_state,
        tol             = 1e-4,
        verbose         = False,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X_scaled)

    states = model.predict(X_scaled)

    means_orig   = scaler.inverse_transform(model.means_)
    return_means = means_orig[:, 0]

    bull_state_id = int(np.argmax(return_means))
    bear_state_id = int(np.argmin(return_means))

    if bull_state_id == bear_state_id:
        sorted_ids    = np.argsort(return_means)
        bear_state_id = int(sorted_ids[0])
        bull_state_id = int(sorted_ids[-1])

    def _label(s: int) -> str:
        if s == bull_state_id: return "Bull"
        if s == bear_state_id: return "Bear"
        return "Neutral"

    df_out = df.copy()
    df_out["HMM_State"] = states
    df_out["Regime"]    = df_out["HMM_State"].map(_label)

    # ── Minimum regime duration filter ────────────────────────────────────────
    raw_regime   = df_out["Regime"].values.copy()
    smooth_regime = _smooth_regimes(raw_regime, MIN_REGIME_BARS)
    df_out["Regime"] = smooth_regime

    # ── HMM_Confidence: row-wise max posterior probability ────────────────────
    proba = model.predict_proba(X_scaled)
    df_out["HMM_Confidence"] = proba.max(axis=1)

    rows = []
    for s in range(n_states):
        mask = df_out["HMM_State"] == s
        rows.append({
            "State":       s,
            "Label":       _label(s),
            "Mean_Return": round(float(df_out.loc[mask, "Returns"].mean()), 6),
            "Volatility":  round(float(df_out.loc[mask, "Returns"].std()),  6),
            "Count":       int(mask.sum()),
            "Avg_Range":   round(float(df_out.loc[mask, "Range"].mean()),   6),
        })
    state_summary = (
        pd.DataFrame(rows)
        .sort_values("Mean_Return", ascending=False)
        .reset_index(drop=True)
    )

    return df_out, bull_state_id, bear_state_id, state_summary, model, scaler
```

- [ ] **Step 2.4: Run smoothing tests**

```bash
.venv/bin/pytest tests/test_hmm_smoothing.py -v
```
Expected: all tests PASS

- [ ] **Step 2.5: Run import smoke tests to verify no regressions**

```bash
.venv/bin/pytest tests/test_imports.py -v
```
Expected: all PASS

- [ ] **Step 2.6: Commit**

```bash
git add models/hmm.py tests/test_hmm_smoothing.py
git commit -m "feat: add MIN_REGIME_BARS smoothing filter and HMM_Confidence to models/hmm.py"
```

---

## Task 3: strategy/backtest.py — partial exit engine

**Files:**
- Modify: `strategy/backtest.py` (full rewrite)
- Create: `tests/test_backtest.py`

---

- [ ] **Step 3.1: Write failing tests**

Create `tests/test_backtest.py`:

```python
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
    # PnL of Bear exit row = 20000 × 0.90 × (57500/50000 - 1) × 1.5 = 20000 × 0.90 × 0.225 = 4050 (approx)
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
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_backtest.py -v 2>&1 | head -30
```
Expected: FAIL — `_make_trade` has wrong signature / imports missing

- [ ] **Step 3.3: Rewrite strategy/backtest.py**

Replace the entire file:

```python
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
        # Old formula (equity as base) is replaced by equity_at_entry × position_fraction.
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
            _reset_position_state()  # inline below via local vars
            in_position = False;  entry_price = 0.0;  peak_price = 0.0
            position_fraction = 1.0;  tiers_fired = set();  equity_at_entry = 0.0
            entry_bar = -1;  last_exit_bar = i
            continue

        # ── 4. Trailing stop ──────────────────────────────────────────────────
        if in_position and check_trailing_stop(price, peak_price, TRAILING_STOP_PCT):
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
                exit_reason="Trailing Stop",
            ))
            in_position = False;  entry_price = 0.0;  peak_price = 0.0
            position_fraction = 1.0;  tiers_fired = set();  equity_at_entry = 0.0
            entry_bar = -1;  last_exit_bar = i
            continue

        # ── 5. Partial exits ──────────────────────────────────────────────────
        if in_position:
            gain_pct = (price / entry_price - 1.0) * 100.0
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
    is_partial   = exit_reason.startswith("Partial")
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
```

- [ ] **Step 3.4: Run backtest tests**

```bash
.venv/bin/pytest tests/test_backtest.py -v
```
Expected: all PASS

- [ ] **Step 3.5: Run full test suite to check no regressions**

```bash
.venv/bin/pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 3.6: Commit**

```bash
git add strategy/backtest.py tests/test_backtest.py
git commit -m "feat: update strategy/backtest.py with partial exit engine, trailing stop, richer trade log"
```

---

## Task 4: strategy/explain.py

**Files:**
- Create: `strategy/explain.py`
- Create: `tests/test_explain.py`

---

- [ ] **Step 4.1: Write failing tests**

Create `tests/test_explain.py`:

```python
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
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_explain.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'strategy.explain'`

- [ ] **Step 4.3: Create strategy/explain.py**

```python
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
```

- [ ] **Step 4.4: Run explain tests**

```bash
.venv/bin/pytest tests/test_explain.py -v
```
Expected: all PASS

- [ ] **Step 4.5: Run full test suite**

```bash
.venv/bin/pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 4.6: Commit**

```bash
git add strategy/explain.py tests/test_explain.py
git commit -m "feat: add strategy/explain.py — scenario calculator and historical replay"
```

---

## Task 5: app/dashboard.py — UI panels

**Files:**
- Modify: `app/dashboard.py`

This task has no automated tests (Streamlit UI). Verification is manual smoke testing.

---

- [ ] **Step 5.1: Add imports at the top of dashboard.py**

After the existing imports (around line 34), add:

```python
from strategy.exits   import build_exit_thresholds, RECOMMENDED_LADDER
from strategy.explain import get_scenario, get_historical_replay
```

- [ ] **Step 5.2: Add sidebar Exit Strategy controls**

After the `chart_bars` slider block (before `st.caption`), add:

```python
    st.divider()
    st.subheader("Exit Strategy")

    position_mode = st.radio(
        "Position Mode",
        options=["recommended", "user_defined"],
        format_func=lambda x: "Recommended" if x == "recommended" else "User Defined",
        help="Recommended uses the built-in 5-tier profit-taking ladder.",
    )

    position_usd = st.number_input(
        "Position Size (USD)",
        min_value=100,
        value=1000,
        step=100,
        help="Hypothetical capital to allocate to one trade.",
    )

    user_exit_ladder = None
    if position_mode == "user_defined":
        with st.expander("Custom Exit Ladder", expanded=True):
            st.caption("Define 5 tiers. Last tier is always 'remainder' (50% of remaining).")
            default_gains = [15, 30, 45, 60, 100]
            default_fracs = [10, 15, 20, 30, 50]
            rows = []
            for k in range(5):
                c1, c2 = st.columns(2)
                gp = c1.number_input(
                    f"Tier {k+1} Gain %", min_value=1, max_value=1000,
                    value=default_gains[k], key=f"gp_{k}",
                )
                sf = c2.number_input(
                    f"Sell %", min_value=1, max_value=99,
                    value=default_fracs[k], key=f"sf_{k}",
                )
                rows.append({"gain_pct": gp, "sell_fraction": sf / 100.0})
            user_exit_ladder = rows
```

- [ ] **Step 5.3: Update load_backtest to accept position_mode**

Replace the existing `load_backtest` function (lines ~118-122):

```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_backtest(ticker: str, period: str, n_states: int,
                  position_mode: str = "recommended") -> tuple:
    """Run backtest for one ticker (cached 1 hour, recommended mode only)."""
    result = load_ticker(ticker, period, n_states)
    return run_backtest(result["df"], position_mode=position_mode)
```

Add a separate cached wrapper for the scenario and replay:

```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_scenario(ticker: str, period: str, n_states: int,
                  position_usd: float) -> dict:
    """Compute scenario for current signal bar (cached 1 hour)."""
    result = load_ticker(ticker, period, n_states)
    return get_scenario(
        result["df"], ticker, position_usd, RECOMMENDED_LADDER
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_replay(ticker: str, period: str, n_states: int) -> list:
    """Compute historical replay (cached 1 hour)."""
    result = load_ticker(ticker, period, n_states)
    return get_historical_replay(result["df"], n=5)
```

- [ ] **Step 5.4: Add Scenario Calculator panel in Dashboard tab**

In the Dashboard tab, after the signal/regime/confirmation row (after `with summary_col:` block, before `st.divider()`), add the scenario panel. Insert after the closing `with summary_col:` block:

```python
        # ── Scenario Calculator (only shown when signal is LONG) ───────────────
        if signal == "LONG":
            try:
                if position_mode == "user_defined" and user_exit_ladder:
                    try:
                        validated_ladder = build_exit_thresholds("user_defined", user_exit_ladder)
                        scenario = get_scenario(
                            df_sel, selected_ticker, position_usd, validated_ladder
                        )
                    except ValueError as e:
                        st.warning(f"Invalid custom ladder: {e} — showing recommended.")
                        scenario = load_scenario(selected_ticker, period, n_states, position_usd)
                else:
                    scenario = load_scenario(selected_ticker, period, n_states, position_usd)

                st.markdown("#### Scenario Calculator")
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("Entry Price",    f"${scenario['entry_price']:,.2f}")
                sc2.metric("HMM Confidence", f"{scenario['hmm_confidence']:.0%}")
                sc3.metric("Regime Bars",    f"{scenario['regime_bars']}h confirmed")
                sc4.metric("Trailing Stop",  f"${scenario['trailing_stop_price']:,.2f}",
                           delta=f"${scenario['trailing_stop_loss']:,.0f} max loss",
                           delta_color="inverse")

                # Exit schedule table
                sched_df = pd.DataFrame(scenario["exit_schedule"])
                sched_df.columns = ["Tier", "Trigger Price ($)", "USD Realised", "USD Remaining"]
                st.dataframe(sched_df, use_container_width=True, hide_index=True)
                st.caption(
                    f"Risk/Reward: {scenario['risk_reward_ratio']:.1f}×  ·  "
                    f"Avg trade duration: {scenario['avg_trade_duration_h']:.0f}h"
                )
            except Exception as e:
                st.warning(f"Scenario unavailable: {e}")
```

- [ ] **Step 5.5: Add Historical Signal Replay in Backtest tab**

In the Backtest tab, before the `# Equity curve chart` block, add:

```python
        # ── Historical Signal Replay ───────────────────────────────────────────
        try:
            replay = load_replay(selected_ticker, period, n_states)
            if replay:
                st.subheader("Last 5 Completed LONG Trades")
                for trade in replay:
                    ret_color   = "#00c96a" if trade["total_return_pct"] >= 0 else "#e03535"
                    pnl_sign    = "+" if trade["pnl_usd"] >= 0 else ""
                    partials_str = "  ".join(
                        f"`{p}`" for p in trade["partials_fired"]
                    ) if trade["partials_fired"] else "*no partial exits*"
                    st.markdown(
                        f"**Trade {trade['trade_num']}** &nbsp; "
                        f"{trade['entry_time'][:10]} → {trade['exit_time'][:10]} "
                        f"({trade['duration_h']}h)&nbsp; | &nbsp;"
                        f"<span style='color:{ret_color}'>"
                        f"**{trade['total_return_pct']:+.1f}%** / "
                        f"{pnl_sign}${trade['pnl_usd']:,.0f}</span> &nbsp; | &nbsp;"
                        f"Exit: *{trade['exit_reason']}* &nbsp; | &nbsp;"
                        f"Regime: {trade['regime_at_entry']} · "
                        f"{trade['confirmations_entry']}/10 conf &nbsp;",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Partials fired: {partials_str}  ·  Peak gain: {trade['peak_gain_pct']:+.1f}%")
                    st.markdown("---")
        except Exception as e:
            st.warning(f"Replay unavailable: {e}")
```

- [ ] **Step 5.6: Update load_backtest call sites to pass position_mode**

There are two `load_backtest(...)` calls in the file (Dashboard tab and Backtest tab). Update both to include `position_mode`:

For user_defined mode with a validated ladder, call `run_backtest` directly (not cached):

```python
# At the top of both backtest call sites, replace:
#   equity_curve, bh_curve, trades_df, metrics = load_backtest(...)
# with:

        if position_mode == "user_defined" and user_exit_ladder:
            try:
                validated_ladder = build_exit_thresholds("user_defined", user_exit_ladder)
                result_data = load_ticker(selected_ticker, period, n_states)
                equity_curve, bh_curve, trades_df, metrics = run_backtest(
                    result_data["df"],
                    position_mode="user_defined",
                    user_exit_ladder=validated_ladder,
                )
            except ValueError as e:
                st.warning(f"Invalid custom ladder: {e} — using recommended.")
                equity_curve, bh_curve, trades_df, metrics = load_backtest(
                    selected_ticker, period, n_states
                )
        else:
            equity_curve, bh_curve, trades_df, metrics = load_backtest(
                selected_ticker, period, n_states
            )
```

- [ ] **Step 5.7: Fix applymap → map deprecation in trade log**

In the Backtest tab, find the `.applymap(color_ret, subset=["Return %"])` call and change it to:

```python
trades_df.style.map(color_ret, subset=["Return %"])
```

- [ ] **Step 5.8: Update trade log caption to show non-partial count**

Change the existing caption that reads `{len(trades_df)} completed trades`:

```python
            n_full = len(trades_df[trades_df["Is Partial"] == False]) if "Is Partial" in trades_df.columns else len(trades_df)
            st.caption(
                f"{n_full} completed trades (+ {len(trades_df) - n_full} partial exits shown) "
                f"· Avg return {metrics['Avg Trade Return (%)']:+.2f}% per trade"
            )
```

- [ ] **Step 5.9: Add README/About tab sections**

In the README tab (`with tab_readme:`), after the existing content (append at the end of the tab):

```python
    st.divider()

    st.subheader("How the Strategy Protects Your Position")
    st.markdown("""
**5-Tier Profit-Taking Ladder**

Rather than holding 100% of a position until a Bear regime exit, the strategy incrementally
realises gains as price advances:

| Tier | Gain from Entry | Fraction Sold |
|---|---|---|
| 1 | +15% | 10% of original position |
| 2 | +30% | 15% of original position |
| 3 | +45% | 20% of original position |
| 4 | +60% | 30% of original position |
| 5 | +100% | 50% of *remaining* position |

By +60%, approximately 75% of your original position has been de-risked into realised gains.
Anything above +100% is held until a Bear regime exit or trailing stop — no further automatic sells.

**Trailing Stop**

Once you are in a position, a moving floor protects against giving back large gains.
If price falls 5% below its peak since entry, the remaining position closes immediately —
regardless of regime. This fires before checking for a Bear regime exit on the same bar.

**3-Bar Regime Filter**

The HMM model requires 3 consecutive hourly bars in a new regime before that regime is
confirmed. A single-candle regime spike is reverted to the prior confirmed regime.
This prevents false signals from transient noise.

**Bear Regime Exit**

When the HMM detects a confirmed Bear regime (3+ consecutive Bear bars), any open
remaining position closes immediately, regardless of current gain or loss.
""")

    st.divider()

    st.subheader("Understanding Bull, Bear, and Neutral Regimes")
    st.markdown("""
The HMM groups all hourly bars into hidden states based on three features: **Returns**
(hourly price change), **Range** (high−low spread), and **Vol_Change** (hourly volume shift).

**Bull** — the state with the highest average hourly return. Typically characterised by
positive price momentum and controlled volatility.

**Bear** — the state with the lowest average hourly return. Associated with negative price
movement or sharp drawdowns.

**Neutral** — all remaining states. Neither strongly bullish nor bearish. A Neutral regime
is **not a sell signal** — open positions remain open during Neutral periods.

**Regime vs Signal:** A regime describes the current market character. A *Signal* is
generated only when the regime is Bull AND at least 8 of 10 technical confirmations pass.
You can be in a Bull regime without a LONG signal if confirmations are weak.

Regime changes take effect only after the 3-bar minimum duration filter confirms them.
""")

    st.divider()

    # Model Parameters table — add new constants
    st.subheader("Model & Strategy Parameters")
    params = {
        "Initial Capital":     "$20,000",
        "Leverage":            "1.5×",
        "Cooldown After Exit": "72 bars (hours)",
        "Min Confirmations":   "8 / 10",
        "HMM States":          str(n_states),
        "MIN_REGIME_BARS":     "3",
        "TRAILING_STOP_PCT":   "5%",
        "Exit Tier 1":         "+15% → sell 10% of position",
        "Exit Tier 2":         "+30% → sell 15% of position",
        "Exit Tier 3":         "+45% → sell 20% of position",
        "Exit Tier 4":         "+60% → sell 30% of position",
        "Exit Tier 5":         "+100% → sell 50% of remaining",
    }
    params_df = pd.DataFrame(params.items(), columns=["Parameter", "Value"])
    st.dataframe(params_df, use_container_width=True, hide_index=True)
```

- [ ] **Step 5.10: Manual smoke test**

```bash
cd /Users/dmd/Desktop/HMM_Quant/HMM_Quant
.venv/bin/streamlit run app/dashboard.py
```

Verify:
1. Dashboard loads without errors
2. Sidebar shows "Exit Strategy" section with Position Mode radio and Position Size input
3. When signal is LONG: Scenario Calculator panel appears below the signal row
4. Backtest tab shows "Last 5 Completed LONG Trades" section above equity chart
5. README tab shows new "How the Strategy Protects Your Position" and "Understanding Regimes" sections
6. Trade log shows new columns (PnL, Position %, Is Partial, etc.)
7. Switching to "User Defined" mode shows the custom ladder expander

- [ ] **Step 5.11: Run full test suite one final time**

```bash
.venv/bin/pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 5.12: Commit**

```bash
git add app/dashboard.py
git commit -m "feat: add scenario calculator, historical replay, and exit strategy controls to dashboard"
```

---

## Final verification

- [ ] Run full test suite:

```bash
.venv/bin/pytest tests/ -v --tb=short
```
Expected: all tests in `test_imports.py`, `test_exits.py`, `test_hmm_smoothing.py`, `test_backtest.py`, `test_explain.py` pass.

- [ ] Confirm new modules are importable:

```bash
.venv/bin/python -c "
from strategy.exits   import RECOMMENDED_LADDER, check_trailing_stop, check_partial_exits
from strategy.explain import get_scenario, get_historical_replay
from models.hmm       import MIN_REGIME_BARS, _smooth_regimes
from strategy.backtest import run_backtest, INITIAL_CAPITAL, LEVERAGE
print('All imports OK')
print('MIN_REGIME_BARS =', MIN_REGIME_BARS)
print('TRAILING_STOP_PCT =', __import__('strategy.exits', fromlist=['TRAILING_STOP_PCT']).TRAILING_STOP_PCT)
"
```
Expected: prints `All imports OK` with correct constant values.
