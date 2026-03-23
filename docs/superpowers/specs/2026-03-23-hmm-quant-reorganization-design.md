# HMM_Quant — Project Reorganization Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Approach:** Option C — Domain-Driven folder structure + full documentation layer

---

## Overview

Restructure HMM_Quant from 4 flat Python files into a domain-driven module layout. Split `data_prep.py` into focused sub-modules, rename and relocate the Streamlit app, move the standalone notebook script, and add three markdown documentation files.

---

## New Folder Structure

```
HMM_Quant/
├── pipeline/
│   ├── __init__.py
│   ├── download.py       # OHLCV fetch from yfinance
│   ├── features.py       # Returns, Range, Vol_Change + IQR clipping
│   └── indicators.py     # EMA, RSI, MACD, ADX, Volume SMA, Momentum, Volatility
├── models/
│   ├── __init__.py
│   └── hmm.py            # GaussianHMM fit, state labelling, state_summary
├── strategy/
│   ├── __init__.py
│   ├── signals.py        # 10-confirmation scoring + get_ticker_data() public API
│   └── backtest.py       # run_backtest(), metrics, trade log
├── app/
│   ├── __init__.py
│   └── dashboard.py      # Streamlit app (renamed from corn_app.py)
├── notebooks/
│   └── hmm_regime_detection.py   # Standalone Jupyter/Colab script (moved as-is)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── STRATEGY.md
│   └── superpowers/specs/        # Design specs (this file)
├── assets/
│   ├── regime_detection.png      # Notebook output image
│   └── project-redesign.html     # Visual design reference
├── README.md                     # Rewritten
├── requirements.txt
└── .gitignore
```

---

## File Mapping

| New File | Source | Action |
|---|---|---|
| `pipeline/download.py` | `data_prep.py` | Split — `_download()`, TICKERS, TICKER_LABELS, REQUIRED_COLS |
| `pipeline/features.py` | `data_prep.py` | Split — `_engineer_features()`, `_robust_clip()`, FEATURE_COLS |
| `pipeline/indicators.py` | `data_prep.py` | Split — `_add_indicators()`, `_compute_adx()` |
| `models/hmm.py` | `data_prep.py` | Split — `_fit_hmm()`, N_STATES, RANDOM_SEED |
| `strategy/signals.py` | `data_prep.py` | Split — `_score_signals()`, `get_ticker_data()`, CONFIRM_COLS, CONFIRM_LABELS |
| `strategy/backtest.py` | `backtest_logic.py` | Move entire file |
| `app/dashboard.py` | `corn_app.py` | Rename + update imports |
| `notebooks/hmm_regime_detection.py` | `hmm_regime_detection.py` | Move as-is |
| `assets/regime_detection.png` | `regime_detection.png` | Move |
| `assets/project-redesign.html` | (already created in assets/) | Already exists — no action needed |
| `README.md` | existing README.md | Rewrite |
| `docs/ARCHITECTURE.md` | — | New |
| `docs/STRATEGY.md` | — | New |

---

## Module Interfaces

### `pipeline/download.py`
- **Exports:** `download_ohlcv(ticker, period, interval) → pd.DataFrame`, `TICKERS`, `TICKER_LABELS`, `REQUIRED_COLS`, `PERIOD`, `INTERVAL`

### `pipeline/features.py`
- **Exports:** `engineer_features(df) → pd.DataFrame`, `robust_clip(series, mult)`, `FEATURE_COLS`

### `pipeline/indicators.py`
- **Exports:** `add_indicators(df) → pd.DataFrame`, `compute_adx(df, period)`

### `models/hmm.py`
- **Exports:** `fit_hmm(df, n_states, random_state) → (df, bull_id, bear_id, state_summary, model, scaler)`, `N_STATES`, `RANDOM_SEED`

### `strategy/signals.py`
- **Exports:** `score_signals(df) → pd.DataFrame`, `get_ticker_data(ticker, period, interval, n_states, rand_seed) → dict`, `CONFIRM_COLS`, `CONFIRM_LABELS`

### `strategy/backtest.py`
- **Exports:** `run_backtest(df, initial_capital, leverage) → (equity_curve, bh_curve, trades_df, metrics)`

---

## Data Flow

```
pipeline/download.py
    → pipeline/features.py
    → pipeline/indicators.py
    → models/hmm.py
    → strategy/signals.py   ← get_ticker_data() orchestrates this chain
    → strategy/backtest.py  ← consumes get_ticker_data() output
    → app/dashboard.py      ← consumes both get_ticker_data() + run_backtest()
```

---

## Documentation Files

### README.md (rewrite)
- Project summary, tickers (BTC, ETH, SOL, ADA), what HMM regime detection does
- Install: `pip install -r requirements.txt`
- Run: `streamlit run app/dashboard.py`
- Brief strategy overview with link to `docs/STRATEGY.md`
- Folder structure overview with link to `docs/ARCHITECTURE.md`

### docs/ARCHITECTURE.md
- Folder map with one-line description per module
- Data flow diagram (text-based)
- Public API reference for each module
- Import dependency overview

### docs/STRATEGY.md
- HMM regime detection: what it is, why 6 states, features used (Returns, Range, Vol_Change)
- Bull/Bear/Neutral auto-labelling logic
- All 10 confirmation signals with thresholds and rationale
- Trade signal rules: LONG (Bull + ≥8 confirmations), SHORT (Bear), NEUTRAL
- Backtest rules: $20k capital, 1.5× leverage, 72-hour cooldown, Bear-exit
- Performance metrics explanation

---

## Import Changes Required

`app/dashboard.py` imports will change from:
```python
from data_prep import (
    get_ticker_data, TICKERS, TICKER_LABELS, CONFIRM_COLS, CONFIRM_LABELS, N_STATES
)
from backtest_logic import run_backtest
```
to:
```python
from strategy.signals import get_ticker_data, CONFIRM_COLS, CONFIRM_LABELS
from pipeline.download import TICKERS, TICKER_LABELS
from models.hmm import N_STATES
from strategy.backtest import run_backtest
```

---

## Known Issues (carry forward, not fixing now)

- `_make_trade()` in `backtest_logic.py` hardcodes the module-level `INITIAL_CAPITAL` constant for `pnl_usd` calculation instead of using the `initial_capital` parameter passed to `run_backtest()`. This means the `pnl_usd` field in the trade log is always relative to $20,000 regardless of what the caller passes. This is a pre-existing bug — marked out-of-scope for this restructure.

## Out of Scope

- No changes to HMM model parameters, strategy logic, or backtest rules
- No new features added
- `hmm_regime_detection.py` is moved as-is (no code changes)
- No `setup.py` or `pyproject.toml` (not packaging as installable library)
- `__pycache__/` directories at the root will become stale after files move — these are already excluded by `.gitignore` and can be deleted locally
- All `__init__.py` files are empty (no convenience re-exports)
