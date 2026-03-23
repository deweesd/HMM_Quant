# HMM_Quant Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure HMM_Quant from 4 flat Python files into a domain-driven module layout and add three markdown documentation files (README, ARCHITECTURE, STRATEGY).

**Architecture:** Split `data_prep.py` into `pipeline/` (download, features, indicators) and `models/` (hmm) sub-modules, with `strategy/` holding signals + backtest. The Streamlit app moves to `app/dashboard.py` with updated imports. The standalone notebook script moves to `notebooks/`.

**Tech Stack:** Python 3.12+, Streamlit, hmmlearn, yfinance, scikit-learn, pandas, numpy, plotly

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `pipeline/__init__.py` | Empty — marks package |
| Create | `pipeline/download.py` | OHLCV download from yfinance |
| Create | `pipeline/features.py` | Returns/Range/Vol_Change + IQR clipping |
| Create | `pipeline/indicators.py` | EMA, RSI, MACD, ADX, Vol SMA, Momentum, Volatility |
| Create | `models/__init__.py` | Empty — marks package |
| Create | `models/hmm.py` | GaussianHMM fit + state labelling |
| Create | `strategy/__init__.py` | Empty — marks package |
| Create | `strategy/signals.py` | 10-confirmation scoring + `get_ticker_data()` orchestrator |
| Create | `strategy/backtest.py` | Backtest engine (moved from `backtest_logic.py`) |
| Create | `app/__init__.py` | Empty — marks package |
| Create | `app/dashboard.py` | Streamlit app (renamed from `corn_app.py`, imports updated) |
| Create | `notebooks/hmm_regime_detection.py` | Standalone analysis script (moved as-is) |
| Move | `assets/regime_detection.png` | Output image from notebook |
| Rewrite | `README.md` | Project overview, install, run, strategy summary |
| Create | `docs/ARCHITECTURE.md` | Module map, data flow, public API reference |
| Create | `docs/STRATEGY.md` | HMM logic, 10 signals, backtest rules |
| Update | `.gitignore` | Add `.venv/`, `.superpowers/` |
| Delete | `data_prep.py` | Replaced by pipeline/ + models/ + strategy/signals.py |
| Delete | `backtest_logic.py` | Replaced by strategy/backtest.py |
| Delete | `corn_app.py` | Replaced by app/dashboard.py |
| Delete | `hmm_regime_detection.py` | Moved to notebooks/ |
| Delete | `regime_detection.png` | Moved to assets/ |

---

## Task 1: Create folder skeleton and smoke test harness

**Files:**
- Create: `pipeline/__init__.py`
- Create: `models/__init__.py`
- Create: `strategy/__init__.py`
- Create: `app/__init__.py`
- Create: `notebooks/` (directory)
- Create: `tests/test_imports.py`

- [ ] **Step 1: Create all empty `__init__.py` files and directories**

```bash
mkdir -p pipeline models strategy app notebooks tests
touch pipeline/__init__.py models/__init__.py strategy/__init__.py app/__init__.py
```

- [ ] **Step 2: Write the import smoke test file**

Create `tests/test_imports.py`:
```python
"""Smoke tests — verify every module can be imported without error."""

def test_pipeline_download_imports():
    from pipeline.download import download_ohlcv, TICKERS, TICKER_LABELS
    from pipeline.download import REQUIRED_COLS, PERIOD, INTERVAL
    assert len(TICKERS) == 4

def test_pipeline_features_imports():
    from pipeline.features import engineer_features, robust_clip, FEATURE_COLS
    assert FEATURE_COLS == ["Returns", "Range", "Vol_Change"]

def test_pipeline_indicators_imports():
    from pipeline.indicators import add_indicators, compute_adx

def test_models_hmm_imports():
    from models.hmm import fit_hmm, N_STATES, RANDOM_SEED
    assert N_STATES == 6

def test_strategy_signals_imports():
    from strategy.signals import score_signals, get_ticker_data
    from strategy.signals import CONFIRM_COLS, CONFIRM_LABELS
    assert len(CONFIRM_COLS) == 10

def test_strategy_backtest_imports():
    from strategy.backtest import run_backtest
```

- [ ] **Step 3: Run tests — expect ALL to fail (modules don't exist yet)**

```bash
cd /Users/dmd/Desktop/HMM_Quant/HMM_Quant
python -m pytest tests/test_imports.py -v 2>&1 | head -40
```
Expected: 6 failures with `ModuleNotFoundError`

- [ ] **Step 4: Commit skeleton**

```bash
git add pipeline/__init__.py models/__init__.py strategy/__init__.py app/__init__.py tests/test_imports.py
git commit -m "chore: scaffold domain-driven folder structure + import smoke tests"
```

---

## Task 2: Create `pipeline/download.py`

**Files:**
- Create: `pipeline/download.py`
- Source: `data_prep.py` lines 40–130 (constants + `_download()`)

- [ ] **Step 1: Create `pipeline/download.py`**

```python
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
```

- [ ] **Step 2: Run the download smoke test**

```bash
python -m pytest tests/test_imports.py::test_pipeline_download_imports -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pipeline/download.py
git commit -m "feat: add pipeline/download.py (OHLCV fetch)"
```

---

## Task 3: Create `pipeline/features.py`

**Files:**
- Create: `pipeline/features.py`
- Source: `data_prep.py` lines 133–174 (`_robust_clip`, `_engineer_features`, `FEATURE_COLS`)

- [ ] **Step 1: Create `pipeline/features.py`**

```python
"""
pipeline/features.py
────────────────────
Feature engineering for HMM training.

Computes Returns, Range, Vol_Change from OHLCV and applies IQR-based
outlier clipping to prevent degenerate HMM covariance matrices.

Public API
──────────
  engineer_features(df) → pd.DataFrame
  robust_clip(series, mult) → pd.Series
  FEATURE_COLS — ["Returns", "Range", "Vol_Change"]
"""

import numpy  as np
import pandas as pd

FEATURE_COLS = ["Returns", "Range", "Vol_Change"]


def robust_clip(series: pd.Series, mult: float) -> pd.Series:
    """Clip to [Q25 - mult×IQR, Q75 + mult×IQR]. Scale-invariant outlier removal."""
    q25, q75 = series.quantile(0.25), series.quantile(0.75)
    iqr = q75 - q25
    if iqr == 0:
        return series
    return series.clip(q25 - mult * iqr, q75 + mult * iqr)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Returns, Range, Vol_Change from OHLCV.
    Drops NaN/inf rows and applies IQR clipping.
    """
    out = df.copy()
    out["Returns"]    = out["Close"].pct_change()
    out["Range"]      = (out["High"] - out["Low"]) / out["Close"]
    out["Vol_Change"] = out["Volume"].pct_change()

    out = out.dropna(subset=FEATURE_COLS)
    out[FEATURE_COLS] = out[FEATURE_COLS].replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=FEATURE_COLS)

    out["Returns"]    = robust_clip(out["Returns"],    mult=10.0)
    out["Range"]      = robust_clip(out["Range"],      mult=10.0)
    out["Vol_Change"] = robust_clip(out["Vol_Change"], mult=5.0)

    return out
```

- [ ] **Step 2: Run smoke test**

```bash
python -m pytest tests/test_imports.py::test_pipeline_features_imports -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pipeline/features.py
git commit -m "feat: add pipeline/features.py (Returns/Range/Vol_Change + IQR clipping)"
```

---

## Task 4: Create `pipeline/indicators.py`

**Files:**
- Create: `pipeline/indicators.py`
- Source: `data_prep.py` lines 177–274 (`_compute_adx`, `_add_indicators`)

- [ ] **Step 1: Create `pipeline/indicators.py`**

```python
"""
pipeline/indicators.py
──────────────────────
Technical indicators for the 10-confirmation signal.

Public API
──────────
  add_indicators(df) → pd.DataFrame
  compute_adx(df, period) → pd.Series
"""

import numpy  as np
import pandas as pd


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder-smoothed Average Directional Index (ADX).
    Uses alpha = 1/period (Wilder smoothing).
    """
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]
    alpha = 1.0 / period

    tr = pd.concat(
        [high - low,
         (high - close.shift(1)).abs(),
         (low  - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)

    up   = high - high.shift(1)
    down = low.shift(1) - low

    plus_dm  = up.where(  (up > down) & (up > 0),   0.0)
    minus_dm = down.where((down > up) & (down > 0),  0.0)

    atr      = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm( alpha=alpha, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr

    denom = (plus_di + minus_di).replace(0, np.nan)
    dx    = 100 * (plus_di - minus_di).abs() / denom
    return dx.ewm(alpha=alpha, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add EMA20, EMA200, RSI, MACD, MACD_Signal, MACD_Hist, ADX,
    Vol_SMA20, Momentum, Volatility to the DataFrame.
    """
    out = df.copy()

    out["EMA20"]  = out["Close"].ewm(span=20,  adjust=False).mean()
    out["EMA200"] = out["Close"].ewm(span=200, adjust=False).mean()

    alpha_rsi = 1.0 / 14
    delta     = out["Close"].diff()
    gain      = delta.clip(lower=0)
    loss      = (-delta.clip(upper=0))
    avg_gain  = gain.ewm(alpha=alpha_rsi, adjust=False).mean()
    avg_loss  = loss.ewm(alpha=alpha_rsi, adjust=False).mean()
    rs        = avg_gain / (avg_loss + 1e-10)
    out["RSI"] = 100 - (100 / (1 + rs))

    ema12               = out["Close"].ewm(span=12, adjust=False).mean()
    ema26               = out["Close"].ewm(span=26, adjust=False).mean()
    out["MACD"]         = ema12 - ema26
    out["MACD_Signal"]  = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_Hist"]    = out["MACD"] - out["MACD_Signal"]

    out["ADX"]      = compute_adx(out, period=14)
    out["Vol_SMA20"] = out["Volume"].rolling(20).mean()
    out["Momentum"]  = (out["Close"] / out["Close"].shift(24) - 1) * 100
    out["Volatility"] = out["Returns"].rolling(24).std() * np.sqrt(24) * 100

    return out
```

- [ ] **Step 2: Run smoke test**

```bash
python -m pytest tests/test_imports.py::test_pipeline_indicators_imports -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pipeline/indicators.py
git commit -m "feat: add pipeline/indicators.py (EMA/RSI/MACD/ADX/Momentum/Volatility)"
```

---

## Task 5: Create `models/hmm.py`

**Files:**
- Create: `models/hmm.py`
- Source: `data_prep.py` lines 280–361 (`_fit_hmm`, N_STATES, RANDOM_SEED)

- [ ] **Step 1: Create `models/hmm.py`**

```python
"""
models/hmm.py
─────────────
Fit GaussianHMM on engineered features and label Bull/Bear/Neutral regimes.

Public API
──────────
  fit_hmm(df, n_states, random_state) →
      (df_out, bull_state_id, bear_state_id, state_summary, model, scaler)
  N_STATES    — default number of HMM hidden states (6)
  RANDOM_SEED — default random seed (42)
"""

import warnings
import numpy  as np
import pandas as pd
from hmmlearn.hmm          import GaussianHMM
from sklearn.preprocessing import StandardScaler

from pipeline.features import FEATURE_COLS

N_STATES    = 6
RANDOM_SEED = 42


def fit_hmm(df: pd.DataFrame, n_states: int = N_STATES, random_state: int = RANDOM_SEED):
    """
    Fit a GaussianHMM on the three scaled features.

    Returns
    ───────
    df_out        — input df with 'HMM_State' and 'Regime' columns added
    bull_state_id — int, state with highest mean return
    bear_state_id — int, state with lowest mean return
    state_summary — pd.DataFrame with one row per state
    model         — fitted GaussianHMM
    scaler        — fitted StandardScaler
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

- [ ] **Step 2: Run smoke test**

```bash
python -m pytest tests/test_imports.py::test_models_hmm_imports -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add models/hmm.py
git commit -m "feat: add models/hmm.py (GaussianHMM fit + Bull/Bear/Neutral labelling)"
```

---

## Task 6: Create `strategy/signals.py`

**Files:**
- Create: `strategy/signals.py`
- Source: `data_prep.py` lines 364–475 (`_score_signals`, `get_ticker_data`, CONFIRM_COLS, CONFIRM_LABELS)

- [ ] **Step 1: Create `strategy/signals.py`**

```python
"""
strategy/signals.py
───────────────────
Score 10 confirmation signals and generate trade signal (LONG/SHORT/NEUTRAL).
Provides get_ticker_data() — the main public API for the full pipeline.

Public API
──────────
  get_ticker_data(ticker, period, interval, n_states, rand_seed) → dict
  score_signals(df) → pd.DataFrame
  CONFIRM_COLS   — list of 10 confirmation column names
  CONFIRM_LABELS — {col_name: human_readable_label}
"""

import warnings
import numpy  as np
import pandas as pd

from pipeline.download   import download_ohlcv, PERIOD, INTERVAL
from pipeline.features   import engineer_features
from pipeline.indicators import add_indicators
from models.hmm          import fit_hmm, N_STATES, RANDOM_SEED

warnings.filterwarnings("ignore")

CONFIRM_COLS = [
    "C1_RSI_lt_80",
    "C2_Mom_gt_1p5",
    "C3_Vol_lt_6",
    "C4_MACD_near_pos",
    "C5_Vol_gt_SMA",
    "C6_ADX_gt_30",
    "C7_Price_gt_EMA20",
    "C8_Price_gt_EMA200",
    "C9_MACD_gt_Signal",
    "C10_RSI_gt_20",
]

CONFIRM_LABELS = {
    "C1_RSI_lt_80":       "RSI < 80  (not overbought)",
    "C2_Mom_gt_1p5":      "Momentum > 1.5%  (24-hr)",
    "C3_Vol_lt_6":        "Volatility < 6%  (24-hr realised)",
    "C4_MACD_near_pos":   "MACD nearing positive (histogram > -0.1% of price)",
    "C5_Vol_gt_SMA":      "Volume > 20-bar SMA",
    "C6_ADX_gt_30":       "ADX > 30  (strong trend)",
    "C7_Price_gt_EMA20":  "Price > EMA 20",
    "C8_Price_gt_EMA200": "Price > EMA 200",
    "C9_MACD_gt_Signal":  "MACD > Signal line  (bullish cross)",
    "C10_RSI_gt_20":      "RSI > 20  (not deeply oversold)",
}

_INDICATOR_COLS = [
    "EMA20", "EMA200", "RSI", "MACD", "MACD_Signal",
    "ADX", "Vol_SMA20", "Momentum", "Volatility",
]


def score_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 10 boolean confirmations, sum into Confirmations, assign Signal."""
    out = df.copy()

    out["C1_RSI_lt_80"]       = out["RSI"] < 80
    out["C2_Mom_gt_1p5"]      = out["Momentum"] > 1.5
    out["C3_Vol_lt_6"]        = out["Volatility"] < 6.0
    out["C4_MACD_near_pos"]   = out["MACD_Hist"] > -(out["Close"] * 0.001)
    out["C5_Vol_gt_SMA"]      = out["Volume"] > out["Vol_SMA20"]
    out["C6_ADX_gt_30"]       = out["ADX"] > 30
    out["C7_Price_gt_EMA20"]  = out["Close"] > out["EMA20"]
    out["C8_Price_gt_EMA200"] = out["Close"] > out["EMA200"]
    out["C9_MACD_gt_Signal"]  = out["MACD"] > out["MACD_Signal"]
    out["C10_RSI_gt_20"]      = out["RSI"] > 20

    out["Confirmations"] = out[CONFIRM_COLS].fillna(False).astype(int).sum(axis=1)

    conditions = [
        (out["Regime"] == "Bull") & (out["Confirmations"] >= 8),
        out["Regime"] == "Bear",
    ]
    out["Signal"] = np.select(conditions, ["LONG", "SHORT"], default="NEUTRAL")

    return out


def get_ticker_data(
    ticker:    str = "BTC-USD",
    period:    str = PERIOD,
    interval:  str = INTERVAL,
    n_states:  int = N_STATES,
    rand_seed: int = RANDOM_SEED,
) -> dict:
    """
    Full pipeline: download → features → indicators → HMM → signals.

    Returns dict with keys: df, bull_state_id, bear_state_id, state_summary, ticker
    """
    raw = download_ohlcv(ticker, period, interval)
    df  = engineer_features(raw)
    df  = add_indicators(df)
    df  = df.dropna(subset=_INDICATOR_COLS).copy()
    df, bull_id, bear_id, summary, _, _ = fit_hmm(df, n_states=n_states, random_state=rand_seed)
    df  = score_signals(df)

    return {
        "df":            df,
        "bull_state_id": bull_id,
        "bear_state_id": bear_id,
        "state_summary": summary,
        "ticker":        ticker,
    }
```

- [ ] **Step 2: Run smoke test**

```bash
python -m pytest tests/test_imports.py::test_strategy_signals_imports -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add strategy/signals.py
git commit -m "feat: add strategy/signals.py (10-confirmation scoring + get_ticker_data orchestrator)"
```

---

## Task 7: Create `strategy/backtest.py`

**Files:**
- Create: `strategy/backtest.py`
- Source: `backtest_logic.py` (full file, moved as-is)

- [ ] **Step 1: Copy `backtest_logic.py` content to `strategy/backtest.py`**

```bash
cp backtest_logic.py strategy/backtest.py
```

Then update the module docstring at the top of `strategy/backtest.py` to reflect the new path:

Change:
```python
////// backtest_logic.py \\\\\\
```
To:
```python
////// strategy/backtest.py \\\\\\
```

- [ ] **Step 2: Run smoke test**

```bash
python -m pytest tests/test_imports.py::test_strategy_backtest_imports -v
```
Expected: PASS

- [ ] **Step 3: Run full smoke test suite**

```bash
python -m pytest tests/test_imports.py -v
```
Expected: ALL 6 PASS

- [ ] **Step 4: Commit**

```bash
git add strategy/backtest.py
git commit -m "feat: add strategy/backtest.py (backtest engine moved from backtest_logic.py)"
```

---

## Task 8: Create `app/dashboard.py` (rename + update imports)

**Files:**
- Create: `app/dashboard.py`
- Source: `corn_app.py` (full file, with import block updated)

- [ ] **Step 1: Copy `corn_app.py` to `app/dashboard.py`**

```bash
cp corn_app.py app/dashboard.py
```

- [ ] **Step 2: Update the import block in `app/dashboard.py`**

Find and replace the import block (lines 27–30):

Old:
```python
from data_prep     import (
    get_ticker_data, TICKERS, TICKER_LABELS, CONFIRM_COLS, CONFIRM_LABELS, N_STATES
)
from backtest_logic import run_backtest
```

New:
```python
from strategy.signals  import get_ticker_data, CONFIRM_COLS, CONFIRM_LABELS
from pipeline.download import TICKERS, TICKER_LABELS
from models.hmm        import N_STATES
from strategy.backtest import run_backtest
```

- [ ] **Step 3: Update the module docstring**

Change `corn_app.py` to `app/dashboard.py` in the top docstring. Also update the run instruction:
```
Run with:
    streamlit run app/dashboard.py
```

- [ ] **Step 4: Verify the app starts without import errors**

```bash
cd /Users/dmd/Desktop/HMM_Quant/HMM_Quant
python -c "import sys; sys.path.insert(0, '.'); import app.dashboard" 2>&1 | head -20
```
Expected: No import errors (Streamlit may warn about running outside context — that is fine)

- [ ] **Step 5: Commit**

```bash
git add app/dashboard.py
git commit -m "feat: add app/dashboard.py (Streamlit app renamed from corn_app.py, imports updated)"
```

---

## Task 9: Move notebook and assets

**Files:**
- Create: `notebooks/hmm_regime_detection.py` (moved from root)
- Move: `assets/regime_detection.png` (from root)

- [ ] **Step 1: Move notebook script**

```bash
cp hmm_regime_detection.py notebooks/hmm_regime_detection.py
```

- [ ] **Step 2: Move regime_detection.png**

```bash
mv regime_detection.png assets/regime_detection.png
```

- [ ] **Step 3: Commit**

```bash
git add notebooks/hmm_regime_detection.py assets/regime_detection.png
git commit -m "chore: move notebook script to notebooks/ and image to assets/"
```

---

## Task 10: Write `docs/ARCHITECTURE.md`

**Files:**
- Create: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Create `docs/ARCHITECTURE.md`**

```markdown
# Architecture

## Folder Structure

```
HMM_Quant/
├── pipeline/          # Data acquisition and feature engineering
│   ├── download.py    # OHLCV fetch from yfinance
│   ├── features.py    # Returns, Range, Vol_Change + IQR clipping
│   └── indicators.py  # EMA, RSI, MACD, ADX, Vol SMA, Momentum, Volatility
├── models/            # Machine learning models
│   └── hmm.py         # GaussianHMM fit + Bull/Bear/Neutral state labelling
├── strategy/          # Trading logic
│   ├── signals.py     # 10-confirmation scoring + get_ticker_data() pipeline API
│   └── backtest.py    # Regime-based backtest engine
├── app/               # Streamlit dashboard
│   └── dashboard.py   # Interactive UI (run with: streamlit run app/dashboard.py)
├── notebooks/         # Standalone analysis scripts
│   └── hmm_regime_detection.py  # Jupyter/Colab-compatible regime visualisation
├── docs/              # Documentation
│   ├── ARCHITECTURE.md
│   └── STRATEGY.md
└── assets/            # Images and design references
    └── regime_detection.png
```

## Data Flow

```
pipeline/download.py        → pd.DataFrame (OHLCV)
    ↓
pipeline/features.py        → pd.DataFrame (+ Returns, Range, Vol_Change)
    ↓
pipeline/indicators.py      → pd.DataFrame (+ EMA, RSI, MACD, ADX, …)
    ↓
models/hmm.py               → pd.DataFrame (+ HMM_State, Regime)
    ↓
strategy/signals.py         → pd.DataFrame (+ Confirmations, Signal)
    ↓
strategy/backtest.py        → equity_curve, trades_df, metrics
    ↓
app/dashboard.py            → Streamlit UI
```

The `get_ticker_data()` function in `strategy/signals.py` orchestrates steps 1–5 as a single call. The dashboard calls `get_ticker_data()` and `run_backtest()` independently.

## Public API Reference

### `pipeline/download.py`
| Symbol | Type | Description |
|--------|------|-------------|
| `download_ohlcv(ticker, period, interval)` | function | Returns flat OHLCV DataFrame |
| `TICKERS` | list | `["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD"]` |
| `TICKER_LABELS` | dict | Maps ticker → short name (e.g. `"BTC-USD"` → `"BTC"`) |
| `PERIOD` | str | Default window: `"730d"` |
| `INTERVAL` | str | Default bar: `"1h"` |

### `pipeline/features.py`
| Symbol | Type | Description |
|--------|------|-------------|
| `engineer_features(df)` | function | Adds Returns, Range, Vol_Change; drops NaN/inf; IQR clips |
| `robust_clip(series, mult)` | function | IQR-based clip: `[Q25 - mult×IQR, Q75 + mult×IQR]` |
| `FEATURE_COLS` | list | `["Returns", "Range", "Vol_Change"]` |

### `pipeline/indicators.py`
| Symbol | Type | Description |
|--------|------|-------------|
| `add_indicators(df)` | function | Adds all 10 technical indicators to DataFrame |
| `compute_adx(df, period)` | function | Wilder-smoothed ADX (period=14 default) |

### `models/hmm.py`
| Symbol | Type | Description |
|--------|------|-------------|
| `fit_hmm(df, n_states, random_state)` | function | Returns `(df, bull_id, bear_id, state_summary, model, scaler)` |
| `N_STATES` | int | Default: `6` |
| `RANDOM_SEED` | int | Default: `42` |

### `strategy/signals.py`
| Symbol | Type | Description |
|--------|------|-------------|
| `get_ticker_data(ticker, period, interval, n_states, rand_seed)` | function | Full pipeline → dict with `df`, `bull_state_id`, `bear_state_id`, `state_summary`, `ticker` |
| `score_signals(df)` | function | Adds 10 confirmation columns + Confirmations + Signal |
| `CONFIRM_COLS` | list | 10 confirmation column names |
| `CONFIRM_LABELS` | dict | Human-readable label per confirmation |

### `strategy/backtest.py`
| Symbol | Type | Description |
|--------|------|-------------|
| `run_backtest(df, initial_capital, leverage)` | function | Returns `(equity_curve, bh_curve, trades_df, metrics)` |
```

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md (module map, data flow, public API reference)"
```

---

## Task 11: Write `docs/STRATEGY.md`

**Files:**
- Create: `docs/STRATEGY.md`

- [ ] **Step 1: Create `docs/STRATEGY.md`**

```markdown
# Strategy Documentation

## Overview

HMM_Quant uses a Hidden Markov Model (HMM) to detect latent market regimes in hourly crypto price data, then generates trade signals when multiple technical indicators confirm the regime.

**Tickers:** BTC-USD, ETH-USD, SOL-USD, ADA-USD
**Data:** Hourly OHLCV via yfinance (up to 730 calendar days)

---

## 1. HMM Regime Detection

### Features

The HMM is trained on three features computed from OHLCV data:

| Feature | Formula | What it captures |
|---------|---------|-----------------|
| Returns | `Close.pct_change()` | Momentum / direction |
| Range | `(High - Low) / Close` | Intrabar volatility |
| Vol_Change | `Volume.pct_change()` | Liquidity shifts |

Features are standardised (zero mean, unit variance) before fitting to prevent ill-conditioned covariance matrices.

### Model

- **Type:** `hmmlearn.hmm.GaussianHMM`, `covariance_type="full"`
- **States:** 6 hidden states (configurable in dashboard: 4–8)
- **Training:** 1000 EM iterations, convergence tolerance 1e-4
- **Fitted independently per ticker** — BTC and ADA have different volatility profiles

### State Labelling

After fitting, states are automatically labelled by mean return:
- **Bull** — state with highest mean hourly return
- **Bear** — state with lowest mean hourly return
- **Neutral** — all remaining states

---

## 2. Confirmation Signals

A signal only fires as LONG when the HMM regime is Bull **and** at least 8 of 10 confirmation signals are true.

| # | Signal | Condition | Rationale |
|---|--------|-----------|-----------|
| C1 | RSI not overbought | RSI < 80 | Avoid buying at peak |
| C2 | Momentum positive | 24-hr return > 1.5% | Confirms upward drift |
| C3 | Low volatility | 24-hr realised vol < 6% | Calmer entry conditions |
| C4 | MACD nearing positive | MACD_Hist > −0.1% of price | Trend turning bullish |
| C5 | Volume surge | Volume > 20-bar SMA | Liquidity confirmation |
| C6 | Strong trend | ADX > 30 | Not a choppy range |
| C7 | Price above EMA20 | Close > EMA20 | Short-term bullish |
| C8 | Price above EMA200 | Close > EMA200 | Long-term bullish |
| C9 | MACD crossover | MACD > Signal line | Bullish momentum cross |
| C10 | RSI not oversold | RSI > 20 | Not in panic territory |

---

## 3. Trade Signals

| Signal | Condition |
|--------|-----------|
| **LONG** | Regime == Bull AND Confirmations ≥ 8 |
| **SHORT** | Regime == Bear (informational — not traded in backtest) |
| **NEUTRAL** | Everything else |

---

## 4. Backtest Rules

| Parameter | Value |
|-----------|-------|
| Starting capital | $20,000 |
| Leverage | 1.5× |
| Entry | Signal == LONG |
| Exit | Regime flips to Bear (hard stop) |
| Cooldown | 72 hours after any exit |
| Position size | 100% of current equity per trade |

### PnL Formula

```
trade_return = (exit_price − entry_price) / entry_price × leverage
new_equity   = old_equity × (1 + trade_return)
```

Equity compounds across trades. At 1.5× leverage, a 2% price move produces a 3% equity move — losses are amplified symmetrically.

### Performance Metrics

| Metric | Description |
|--------|-------------|
| Total Return | Strategy equity growth from start to end (%) |
| Buy & Hold | Passive hold return over same period (%) |
| Alpha | Total Return minus Buy & Hold (percentage points) |
| Win Rate | % of completed trades that were profitable |
| Max Drawdown | Largest peak-to-trough equity decline (%) |
| Sharpe Ratio | Annualised Sharpe using hourly bars (8760 hrs/yr, 24/7 crypto) |

---

## 5. Disclaimer

This tool is for educational and research purposes only. It does not constitute financial advice. Past backtested performance does not guarantee future results.
```

- [ ] **Step 2: Commit**

```bash
git add docs/STRATEGY.md
git commit -m "docs: add STRATEGY.md (HMM logic, confirmation signals, backtest rules)"
```

---

## Task 12: Rewrite `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` content**

```markdown
# HMM_Quant

Regime-based crypto trading dashboard powered by Hidden Markov Models.

Detects latent market regimes in hourly BTC, ETH, SOL, and ADA data using a 6-state GaussianHMM, then generates trade signals when 8 of 10 technical confirmation signals align with a Bull regime. Includes a Streamlit dashboard with live regime detection, signal display, and backtesting.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run app/dashboard.py
```

---

## Project Structure

```
HMM_Quant/
├── pipeline/      # Data download and feature engineering
├── models/        # GaussianHMM regime detection
├── strategy/      # Signal scoring and backtesting
├── app/           # Streamlit dashboard
├── notebooks/     # Standalone Jupyter/Colab analysis scripts
├── docs/          # Architecture and strategy documentation
└── assets/        # Images and design references
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full module map and data flow.

---

## Strategy

The system uses a 3-feature HMM (Returns, Intrabar Range, Volume Change) to classify each hourly bar into one of 6 regimes. States are automatically labelled Bull (highest mean return) and Bear (lowest mean return).

A **LONG** signal fires when:
- Current regime is Bull
- At least 8 of 10 technical confirmation signals are true (RSI, MACD, ADX, EMA, Momentum, Volatility, Volume)

See [docs/STRATEGY.md](docs/STRATEGY.md) for the full signal table and backtest rules.

---

## Tickers

| Ticker | Name |
|--------|------|
| BTC-USD | Bitcoin |
| ETH-USD | Ethereum |
| SOL-USD | Solana |
| ADA-USD | Cardano |

---

## Dependencies

See `requirements.txt`. Key libraries: `streamlit`, `hmmlearn`, `yfinance`, `scikit-learn`, `plotly`, `pandas`, `numpy`.

---

*For educational purposes only. Not financial advice.*
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with project overview, quick start, structure, strategy summary"
```

---

## Task 13: Update `.gitignore` and clean up old files

**Files:**
- Modify: `.gitignore`
- Delete: `data_prep.py`, `backtest_logic.py`, `corn_app.py`, `hmm_regime_detection.py` (root), `regime_detection.png` (root)

- [ ] **Step 1: Update `.gitignore`**

Replace `.gitignore` content with:
```
__pycache__/
*.pyc
.venv/
.superpowers/
*.DS_Store
```

- [ ] **Step 2: Delete the old flat files from root**

```bash
git rm data_prep.py backtest_logic.py corn_app.py hmm_regime_detection.py
```

Note: `regime_detection.png` was already moved to `assets/` in Task 9 — confirm it's not still in the root:
```bash
ls regime_detection.png 2>/dev/null && echo "still exists" || echo "already gone"
```
If it still exists at root: `git rm regime_detection.png`

- [ ] **Step 3: Stage everything and commit**

```bash
git add .gitignore
git add -A
git commit -m "chore: remove old flat files, update .gitignore (.venv, .superpowers)"
```

---

## Task 14: Final verification and push

- [ ] **Step 1: Run full smoke test suite one last time**

```bash
python -m pytest tests/test_imports.py -v
```
Expected: ALL 6 PASS

- [ ] **Step 2: Verify the app launches without errors**

```bash
python -c "
import sys
sys.path.insert(0, '.')
from strategy.signals  import get_ticker_data, CONFIRM_COLS, CONFIRM_LABELS
from pipeline.download import TICKERS, TICKER_LABELS
from models.hmm        import N_STATES
from strategy.backtest import run_backtest
print('All imports OK')
print(f'Tickers: {TICKERS}')
print(f'N_STATES: {N_STATES}')
print(f'Confirmations: {len(CONFIRM_COLS)}')
"
```
Expected:
```
All imports OK
Tickers: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD']
N_STATES: 6
Confirmations: 10
```

- [ ] **Step 3: Confirm final folder structure**

```bash
find . -not -path './.git/*' -not -path './.venv/*' -not -path './__pycache__/*' -type f | sort
```

Expected output should match the spec's target structure (no old flat Python files at root).

- [ ] **Step 4: Push to GitHub**

```bash
git push origin main
```

---

## Summary of Commits

1. `chore: scaffold domain-driven folder structure + import smoke tests`
2. `feat: add pipeline/download.py (OHLCV fetch)`
3. `feat: add pipeline/features.py (Returns/Range/Vol_Change + IQR clipping)`
4. `feat: add pipeline/indicators.py (EMA/RSI/MACD/ADX/Momentum/Volatility)`
5. `feat: add models/hmm.py (GaussianHMM fit + Bull/Bear/Neutral labelling)`
6. `feat: add strategy/signals.py (10-confirmation scoring + get_ticker_data orchestrator)`
7. `feat: add strategy/backtest.py (backtest engine moved from backtest_logic.py)`
8. `feat: add app/dashboard.py (Streamlit app renamed from corn_app.py, imports updated)`
9. `chore: move notebook script to notebooks/ and image to assets/`
10. `docs: add ARCHITECTURE.md (module map, data flow, public API reference)`
11. `docs: add STRATEGY.md (HMM logic, confirmation signals, backtest rules)`
12. `docs: rewrite README with project overview, quick start, structure, strategy summary`
13. `chore: remove old flat files, update .gitignore (.venv, .superpowers)`
