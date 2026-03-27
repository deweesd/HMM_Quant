# HMM_Quant

Regime-based crypto trading dashboard powered by Hidden Markov Models.

Detects latent market regimes in hourly BTC, ETH, SOL, and ADA data using a 6-state GaussianHMM, then generates trade signals when 8 of 10 technical confirmation signals align with a Bull regime. Includes a Streamlit dashboard with live regime detection, signal display, and backtesting.

Main app can be found here: btgtraders.com

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
