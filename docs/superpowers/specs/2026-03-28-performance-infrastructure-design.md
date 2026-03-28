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

**Directory creation:** `/data/cache/` is created at application startup via `os.makedirs("/data/cache/", exist_ok=True)` in `cache.py`'s module-level init. It must NOT be created in the Dockerfile — when Railway mounts a volume at `/data`, the mount overlay replaces any directory created at build time, making it invisible at runtime.

**Cache scope:** The scheduler pre-computes only the default parameters (`period=730d`, `n_states=6`) for all 4 tickers. If a user selects a non-default combination (e.g. `period=365d` or `n_states=4`), the cache will miss and the app falls back to live computation with a spinner. This is an acceptable limitation at current scale; the default params cover the primary use case.

**Cache file naming:** `{ticker}_{period}_{n_states}.pkl`
Examples: `BTC-USD_730d_6.pkl`, `ETH-USD_730d_6.pkl`

**Manifest:** A `manifest.json` file alongside the pickles stores the last-refreshed timestamp per ticker as ISO strings. The dashboard reads this directly to display "Data as of HH:MM UTC" — no separate `cache_age_minutes()` function is needed.

**TTL:** 70 minutes (slightly over 60 to avoid boundary race conditions where the scheduler hasn't run yet when the hour turns).

**API:**
- `write_cache(ticker, period, n_states, data)` — pickle data to disk, update manifest
- `read_cache(ticker, period, n_states)` → dict or None — returns None if file missing or older than TTL
- `get_last_refreshed(ticker)` → str or None — reads manifest for display in dashboard

### Component 2: Background Scheduler (`pipeline/scheduler.py`)

Uses `APScheduler` 3.x (`BackgroundScheduler`) running inside the same Streamlit process. No additional Railway service required.

**Singleton pattern:** The scheduler must be a true process-level singleton — one instance per worker process, shared across all user sessions. The correct pattern is `st.cache_resource`, which Streamlit guarantees to run once per process and reuse the result across all sessions and reruns. Using `st.session_state` would be wrong here: it is per-session, meaning one scheduler per concurrent browser tab, causing thread pile-up and redundant yfinance calls under multiple users.

```python
@st.cache_resource
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_all_tickers, "interval", minutes=60)
    scheduler.start()
    return scheduler
```

**Startup behaviour:** On first call, `refresh_all_tickers()` is invoked immediately if any ticker's cache is missing or stale, before entering the regular 60-minute cadence.

**Refresh function:** Calls `get_ticker_data()` for all 4 tickers with default params (`period=730d`, `n_states=6`), then writes results to disk via `cache.py`.

**Logging:** A `logging.info` line is emitted at scheduler start and on each refresh cycle (success or failure) so Railway logs confirm the scheduler is running. Without this, a broken scheduler silently falls back to live compute on every load with no visible indication.

**Error handling:** Exceptions during refresh are caught, logged as `logging.error`, and do not crash the app. The last successful cache is served until a fresh refresh completes.

**APScheduler version pin:** `apscheduler>=3.10.0,<4.0.0` — APScheduler 4.x has a breaking API (removes `BackgroundScheduler`); the upper bound prevents a silent breakage on future `pip install`.

### Component 3: Updated Dashboard Loader

`load_ticker()` in `dashboard.py` is updated to:
1. Call `start_scheduler()` (idempotent via `st.cache_resource`) to ensure the scheduler is running
2. Check disk cache via `cache.read_cache()` — return immediately if fresh
3. Fall back to live `get_ticker_data()` with a `st.spinner` if cache is cold
4. Write the live result back to disk after computing it

The "Data as of HH:MM UTC" label reads from `cache.get_last_refreshed(ticker)` via the manifest.

### Component 4: Railway Persistent Volume

**Prerequisite (manual step in Railway dashboard):**
1. Open the Railway project → service → **Volumes** tab
2. Create a new volume, mount path: `/data`
3. Redeploy the service

This is required before deployment. Without it, `/data` does not exist at runtime, every cache write fails, and the fallback live-compute path runs on every load with no error visible to users.

`requirements.txt` updated to add `apscheduler>=3.10.0,<4.0.0`.

### Component 5: Cloudflare DNS Proxy

Cloudflare free tier is placed in front of Railway as a reverse proxy for btgtraders.com.

**Setup steps (manual, outside codebase):**
1. Add btgtraders.com to Cloudflare (free plan) at dash.cloudflare.com
2. In Namecheap: replace default nameservers with the two Cloudflare nameservers shown during setup
3. In Cloudflare DNS: add a CNAME record — **Name:** `btgtraders.com`, **Target:** Railway's public domain, **Proxy:** enabled (orange cloud)
   - Note: standard DNS prohibits CNAMEs at the zone apex. Cloudflare handles this transparently via "CNAME Flattening" when proxy is enabled — it works correctly even though the DNS record type shown says CNAME. Do not add an A record pointing to Railway's IP; Railway's IPs can change and doing so would bypass Cloudflare's origin hiding.
4. SSL/TLS mode in Cloudflare: set to **Full** (not Flexible) — Railway already terminates HTTPS, so Flexible would cause a redirect loop

**What this provides:**
- Origin IP hidden from public (Railway's IP obscured behind Cloudflare)
- Free DDoS protection (L3/L4/L7)
- Automatic HTTPS with Cloudflare's SSL cert
- Edge caching of Streamlit's static JS/CSS bundles (~200–500ms faster first paint)
- WebSocket passthrough supported on free tier (required for Streamlit)

**No code changes required** for Cloudflare — it is purely a DNS/network configuration.

---

## Repo Cleanup

### Files and directories to delete

| Path | Reason |
|------|--------|
| `mockups/` (entire directory) | Design artifacts (`dashboard-redesign.html`, `header-redesign.html`), now implemented |
| `assets/project-redesign.html` | Old redesign mockup |
| `docs/mockups/` (entire directory) | Contains `2026-03-25-live-tab-enhancements.html`; no longer needed |
| `docs/superpowers/` (entire directory) | Claude Code internal plans/specs — dev tooling, not project code |
| `notebooks/hmm_regime_detection.py` | Early exploration script, not part of deployed app |
| `.devcontainer/` | VS Code devcontainer config, not needed for Railway |
| `runtime.txt` | Superseded by Dockerfile |

### Git tracked file removal

`docs/superpowers/` is currently tracked by git. Simply adding it to `.gitignore` does not remove it from the index. The cleanup commit must run:
```
git rm -r --cached docs/superpowers/
```
in addition to deleting the directory and adding the `.gitignore` entry.

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
[APScheduler — every 60 min, process-level singleton via st.cache_resource]
    └── get_ticker_data(ticker, 730d, 6) for all 4 tickers
            └── yfinance download + HMM fit
                    └── cache.write_cache() → /data/cache/{ticker}.pkl
                            └── manifest.json updated

[User visits btgtraders.com]
    └── Cloudflare edge (static asset cache, DDoS shield)
            └── Railway container
                    └── Streamlit load_ticker()
                            └── cache.read_cache() → instant return
                                    (fallback: live compute + spinner + write to disk)
```

---

## Success Criteria

- Page load after container restart: < 2 seconds (from ~30–60s) for default params
- Cache files present and fresh on Railway persistent volume after first scheduler run
- All 4 tickers pre-computed on default params (730d, n_states=6)
- Railway logs show scheduler start message and periodic refresh log lines
- btgtraders.com resolves through Cloudflare proxy (verifiable via `dig btgtraders.com` — answer should show Cloudflare IPs)
- GitHub repo contains no `mockups/`, `docs/superpowers/`, `notebooks/`, or `.devcontainer/` directories
- `apscheduler>=3.10.0,<4.0.0` present in `requirements.txt`
