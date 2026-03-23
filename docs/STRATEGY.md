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
