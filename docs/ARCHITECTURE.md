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
