# HMM_Quant

Regime-based crypto trading dashboard powered by Hidden Markov Models.

Detects latent market regimes in hourly BTC, ETH, SOL, and ADA data using a 6-state GaussianHMM, then generates trade signals when 8 of 10 technical confirmation signals align with a Bull regime. Includes a live dashboard with regime detection, signal display, and backtesting.

**Live app: [btgtraders.com](https://btgtraders.com)**


---

## Hosting & Infrastructure

The app runs on **Railway** (railway.app) — a production-grade cloud platform — serving a containerized Streamlit application via Docker. This replaces the previous Streamlit Cloud deployment and eliminates cold starts, giving users an always-warm, instant-loading experience.

| Layer | Technology |
|---|---|
| Frontend / UI | Streamlit (Python) |
| Charting | Plotly |
| Containerization | Docker (python:3.11-slim) |
| Hosting | Railway (Hobby plan, us-west2) |
| Domain | btgtraders.com via Namecheap |
| SSL | Auto-provisioned via Railway (Let's Encrypt) |
| Market Data | yfinance (Yahoo Finance) |
| Regime Model | hmmlearn GaussianHMM |

---

## Quick Start (Local Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard locally
streamlit run app/dashboard.py
```

The app is also fully containerized for local Docker use:

```bash
docker build -t hmm-quant .
docker run -p 8501:8501 hmm-quant
# Visit http://localhost:8501
```

---

## Project Structure

```
HMM_Quant/
├── app/           # Streamlit dashboard and CSS design system
├── pipeline/      # Data download and feature engineering
├── models/        # GaussianHMM regime detection
├── strategy/      # Signal scoring and backtesting
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

## Deployment

The app auto-deploys to Railway on every push to `main`. No manual steps required.

Key deployment files:
- `Dockerfile` — container definition, Python 3.11, port 8501
- `railway.toml` — forces Dockerfile builder
- `.streamlit/config.toml` — headless server config

---

*For educational purposes only. Not financial advice.*
