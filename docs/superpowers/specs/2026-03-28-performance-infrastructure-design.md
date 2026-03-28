# Performance & Infrastructure Design
**Date:** 2026-03-28
**Status:** Approved

## Problem

btgtraders.com (Railway-hosted Streamlit app) has a slow first load. On every cold start — triggered by container restart or in-memory cache expiry — the app synchronously downloads 730 days of hourly OHLCV data from yfinance (~17,500 bars per ticker) and re-fits the HMM model for the selected ticker. This blocks page render for 30–60 seconds.

Secondary concerns: the GitHub repo contains dev tooling artifacts and mockup files that obscure the actual project, and the site has no CDN or security proxy in front of it.

## Goals

1. Reduce cold-start page load to under 2 seconds
2. Ensure pre-computed data survives Railway container restarts
3. Maintain hourly signal freshness (sufficient for hourly-bar trading strategy)
4. Secure and accelerate btgtraders.com with Cloudflare (free tier)
5. Clean up the GitHub repo to contain only what is needed to understand and run the app

## Non-Goals

- Real-time (sub-minute) data streaming
- Migrating away from Streamlit
- Account creation or user auth (deferred)
- Switching hosting providers

---

## Design

### Component 1: Disk Cache Layer (`pipeline/cache.py`)

A cache manager that reads and writes pre-computed pipeline results to Railway's persistent volume, mounted at `/data/cache/`.

**Cache file naming:** `{ticker}_{period}_{n_states}.pkl`
Examples: `BTC-USD_730d_6.pkl`, `ETH-USD_730d_6.pkl`

**Manifest:** A `manifest.json` file alongside the pickles stores the last-refreshed timestamp per ticker. The dashboard uses this to display "Data as of HH:MM UTC" to users.

**API:**
- `write_cache(ticker, period, n_states, data)` — pickle data to disk
- `read_cache(ticker, period, n_states)` → dict or None — returns None if file missing or older than TTL
- `cache_age_minutes(ticker, period, n_states)` → float — used by dashboard to show freshness
- `TTL = 70` minutes (slightly over 1 hour to avoid race conditions at the boundary)

### Component 2: Background Scheduler (`pipeline/scheduler.py`)

Uses `APScheduler` (BackgroundScheduler) running inside the same Streamlit process. No additional Railway service required.

**Startup behaviour:** On first import, the scheduler checks all 4 tickers. Any ticker whose cache file is missing or stale triggers an immediate refresh before the scheduler enters its regular cadence.

**Schedule:** Refresh all 4 tickers every 60 minutes.

**Refresh function:** Calls `get_ticker_data()` for each ticker with default params (`period=730d`, `n_states=6`), then writes result to disk via `cache.py`.

**Error handling:** Exceptions during refresh are logged but do not crash the app. Stale cache is served until a successful refresh completes.

**Singleton guard:** The scheduler is started once via a module-level flag checked against `st.session_state` to prevent APScheduler from being instantiated on every Streamlit rerun.

### Component 3: Updated Dashboard Loader

`load_ticker()` in `dashboard.py` is updated to:
1. Check disk cache via `cache.read_cache()` — return immediately if fresh
2. Fall back to live `get_ticker_data()` with a `st.spinner` if cache is cold
3. Write the live result back to disk after computing it

This means: after the first scheduler run, all subsequent page loads (including after container restarts) are near-instant reads from disk.

### Component 4: Railway Persistent Volume

A Railway volume is mounted at `/data` in the service settings. This directory persists across container restarts and redeployments.

`Dockerfile` updated to create `/data/cache/` at build time so the directory exists before the first write.

`requirements.txt` updated to add `apscheduler>=3.10.0`.

### Component 5: Cloudflare DNS Proxy

Cloudflare free tier is placed in front of Railway as a reverse proxy for btgtraders.com.

**Setup steps (manual, outside codebase):**
1. Add btgtraders.com to Cloudflare (free plan)
2. In Namecheap: replace default nameservers with Cloudflare's two assigned nameservers
3. In Cloudflare DNS: add a CNAME record pointing `btgtraders.com` → Railway's public domain, with **Proxy enabled** (orange cloud)
4. SSL/TLS mode: set to **Full** (not Flexible) since Railway already terminates HTTPS

**What this provides:**
- Origin IP hidden from public (Railway's IP obscured behind Cloudflare)
- Free DDoS protection (L3/L4/L7)
- Automatic HTTPS with Cloudflare's SSL cert
- Edge caching of Streamlit's static JS/CSS bundles (~200–500ms faster first paint)
- WebSocket passthrough supported on free tier (required for Streamlit)

**No code changes required** for Cloudflare — it is purely a DNS/network configuration.

---

## Repo Cleanup

### Files to delete

| Path | Reason |
|------|--------|
| `mockups/dashboard-redesign.html` | Design artifact, now implemented |
| `mockups/header-redesign.html` | Design artifact, now implemented |
| `assets/project-redesign.html` | Old redesign mockup |
| `docs/mockups/2026-03-25-live-tab-enhancements.html` | Design artifact |
| `docs/superpowers/` | Claude Code internal plans/specs — dev tooling, not project code |
| `notebooks/hmm_regime_detection.py` | Early exploration script, not part of deployed app |
| `.devcontainer/` | VS Code devcontainer config, not needed for Railway |
| `runtime.txt` | Superseded by Dockerfile |

### Updates to `.gitignore`

Add:
```
docs/superpowers/
.pytest_cache/
notebooks/
```

### Target repo structure after cleanup

```
HMM_Quant/
├── app/
│   ├── __init__.py
│   ├── css.py
│   └── dashboard.py
├── models/
│   ├── __init__.py
│   └── hmm.py
├── pipeline/
│   ├── __init__.py
│   ├── cache.py          ← new
│   ├── download.py
│   ├── features.py
│   ├── indicators.py
│   └── scheduler.py      ← new
├── strategy/
│   ├── __init__.py
│   ├── backtest.py
│   ├── exits.py
│   ├── explain.py
│   └── signals.py
├── tests/
│   └── ...
├── docs/
│   ├── ARCHITECTURE.md
│   └── STRATEGY.md
├── assets/
│   └── regime_detection.png
├── .streamlit/
│   └── config.toml
├── .gitignore
├── Dockerfile
├── railway.toml
├── requirements.txt
└── README.md
```

---

## Data Flow

```
[APScheduler — every 60 min]
    └── get_ticker_data(ticker, 730d, 6)
            └── yfinance download + HMM fit
                    └── cache.write_cache() → /data/cache/{ticker}.pkl

[User visits btgtraders.com]
    └── Cloudflare edge (static asset cache, DDoS shield)
            └── Railway container
                    └── Streamlit load_ticker()
                            └── cache.read_cache() → instant return
                                    (fallback: live compute + spinner)
```

---

## Success Criteria

- Page load after container restart: < 2 seconds (from ~30–60s)
- Cache files present and fresh on Railway persistent volume after first scheduler run
- All 4 tickers pre-computed, not just the selected one
- btgtraders.com resolves through Cloudflare proxy (verifiable via `dig btgtraders.com`)
- GitHub repo contains no mockup HTML files or `docs/superpowers/` directory
- `apscheduler` added to `requirements.txt`
