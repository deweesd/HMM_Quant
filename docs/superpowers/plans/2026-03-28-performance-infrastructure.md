# Performance & Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate 30–60s cold-start load times by pre-computing all 4 tickers on a 1-hour background schedule, persisted to Railway's disk volume so restarts don't blow the cache.

**Architecture:** A new `pipeline/cache.py` reads/writes pickle files to `/data/cache/`. A new `pipeline/scheduler.py` runs APScheduler as a process-level singleton (via `st.cache_resource`) that warms cold tickers on startup and refreshes all tickers every 60 minutes. `dashboard.py`'s `load_ticker()` reads from disk first, falls back to live compute only on cache miss.

**Tech Stack:** Python 3.11, APScheduler 3.x (BackgroundScheduler), pickle, Streamlit `st.cache_resource`, Railway persistent volume at `/data`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pipeline/cache.py` | **Create** | Read/write pre-computed results to disk; manage manifest timestamps |
| `pipeline/scheduler.py` | **Create** | APScheduler singleton; warm stale tickers on startup; refresh every 60 min |
| `app/dashboard.py` | **Modify** | `load_ticker()` reads disk cache first; calls `_start_scheduler()` at module level |
| `requirements.txt` | **Modify** | Add `apscheduler>=3.10.0,<4.0.0` |
| `Dockerfile` | **No change** | Directory created at runtime by cache.py, not at build time |
| `tests/test_cache.py` | **Create** | Unit tests for cache read/write/TTL/manifest |
| `tests/test_scheduler.py` | **Create** | Unit tests for refresh_all_tickers logic |

---

## Task 1: Repo Cleanup

**Files:**
- Delete: `mockups/` (entire directory)
- Delete: `assets/project-redesign.html`
- Delete: `docs/mockups/` (entire directory)
- Delete: `docs/superpowers/` (entire directory — but keep this plan file first, see step below)
- Delete: `notebooks/hmm_regime_detection.py`
- Delete: `.devcontainer/`
- Delete: `runtime.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Remove entire docs/superpowers/ directory from git index**

```bash
git rm -r --cached docs/superpowers/
```

- [ ] **Step 2: Delete files and directories from disk**

```bash
rm -rf mockups/
rm -f assets/project-redesign.html
rm -rf docs/mockups/
rm -rf docs/superpowers/
rm -rf notebooks/
rm -rf .devcontainer/
rm -f runtime.txt
```

- [ ] **Step 3: Update `.gitignore`**

Add these lines to `.gitignore`:
```
docs/superpowers/
.pytest_cache/
notebooks/
```

- [ ] **Step 4: Verify nothing critical was removed**

```bash
ls app/ pipeline/ strategy/ models/ tests/ docs/
```
Expected: all 6 directories present with their Python files intact.

- [ ] **Step 5: Commit cleanup**

```bash
git add -A
git commit -m "chore: remove mockups, notebooks, devcontainer, superpowers artifacts"
```

---

## Task 2: `pipeline/cache.py` — Disk Cache Layer

**Files:**
- Create: `pipeline/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cache.py`:

```python
"""Tests for pipeline/cache.py disk cache layer."""
import json
import os
import time

import pytest


@pytest.fixture(autouse=True)
def patch_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    # Force reimport so CACHE_DIR env var is picked up
    import importlib
    import pipeline.cache
    importlib.reload(pipeline.cache)
    yield
    importlib.reload(pipeline.cache)


def test_read_cache_returns_none_when_missing():
    from pipeline.cache import read_cache
    assert read_cache("BTC-USD", "730d", 6) is None


def test_write_and_read_cache_roundtrip():
    from pipeline.cache import write_cache, read_cache
    data = {"ticker": "BTC-USD", "value": 42}
    write_cache("BTC-USD", "730d", 6, data)
    result = read_cache("BTC-USD", "730d", 6)
    assert result == data


def test_read_cache_returns_none_when_stale(monkeypatch):
    from pipeline.cache import write_cache, read_cache
    import pipeline.cache as cache_mod
    monkeypatch.setattr(cache_mod, "TTL_MINUTES", 0)
    write_cache("BTC-USD", "730d", 6, {"x": 1})
    time.sleep(0.05)
    assert read_cache("BTC-USD", "730d", 6) is None


def test_different_keys_do_not_collide():
    from pipeline.cache import write_cache, read_cache
    write_cache("BTC-USD", "730d", 6, {"ticker": "BTC"})
    write_cache("ETH-USD", "730d", 6, {"ticker": "ETH"})
    assert read_cache("BTC-USD", "730d", 6)["ticker"] == "BTC"
    assert read_cache("ETH-USD", "730d", 6)["ticker"] == "ETH"


def test_manifest_updated_on_write():
    from pipeline.cache import write_cache, get_last_refreshed
    write_cache("BTC-USD", "730d", 6, {"x": 1})
    ts = get_last_refreshed("BTC-USD")
    assert ts is not None
    assert "UTC" in ts


def test_get_last_refreshed_returns_none_when_no_manifest():
    from pipeline.cache import get_last_refreshed
    assert get_last_refreshed("BTC-USD") is None


def test_get_last_refreshed_returns_none_for_unknown_ticker():
    from pipeline.cache import write_cache, get_last_refreshed
    write_cache("BTC-USD", "730d", 6, {"x": 1})
    assert get_last_refreshed("ETH-USD") is None
```

- [ ] **Step 2: Run tests — confirm they all fail**

```bash
pytest tests/test_cache.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` — `pipeline/cache.py` doesn't exist yet.

- [ ] **Step 3: Implement `pipeline/cache.py`**

```python
"""
pipeline/cache.py
─────────────────
Disk cache for pre-computed pipeline results.

Reads/writes pickle files to CACHE_DIR (default: /data/cache).
Override with CACHE_DIR environment variable (used in tests).

Public API
──────────
  write_cache(ticker, period, n_states, data)
  read_cache(ticker, period, n_states)  → dict | None
  get_last_refreshed(ticker)            → str | None
"""

import json
import logging
import os
import pickle
from datetime import datetime, timezone

CACHE_DIR = os.environ.get("CACHE_DIR", "/data/cache")
TTL_MINUTES = 70
_MANIFEST_FILENAME = "manifest.json"

logger = logging.getLogger(__name__)


def _ensure_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(ticker: str, period: str, n_states: int) -> str:
    return os.path.join(CACHE_DIR, f"{ticker}_{period}_{n_states}.pkl")


def _manifest_path() -> str:
    return os.path.join(CACHE_DIR, _MANIFEST_FILENAME)


def write_cache(ticker: str, period: str, n_states: int, data: dict) -> None:
    """Pickle data to disk and update the manifest timestamp."""
    _ensure_dir()
    path = _cache_path(ticker, period, n_states)
    with open(path, "wb") as f:
        pickle.dump(data, f)
    _update_manifest(ticker)
    logger.info("Cache written: %s", path)


def read_cache(ticker: str, period: str, n_states: int) -> dict | None:
    """Return cached data if present and within TTL, else None."""
    path = _cache_path(ticker, period, n_states)
    if not os.path.exists(path):
        return None
    age_minutes = (datetime.now(timezone.utc).timestamp() - os.path.getmtime(path)) / 60
    if age_minutes > TTL_MINUTES:
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def get_last_refreshed(ticker: str) -> str | None:
    """Return 'HH:MM UTC' string of last refresh for ticker, or None."""
    mpath = _manifest_path()
    if not os.path.exists(mpath):
        return None
    with open(mpath) as f:
        manifest = json.load(f)
    return manifest.get(ticker)


def _update_manifest(ticker: str) -> None:
    mpath = _manifest_path()
    manifest: dict = {}
    if os.path.exists(mpath):
        with open(mpath) as f:
            manifest = json.load(f)
    manifest[ticker] = datetime.now(timezone.utc).strftime("%H:%M UTC")
    with open(mpath, "w") as f:
        json.dump(manifest, f)
```

- [ ] **Step 4: Run tests — confirm they all pass**

```bash
pytest tests/test_cache.py -v
```
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/cache.py tests/test_cache.py
git commit -m "feat: add disk cache layer (pipeline/cache.py)"
```

---

## Task 3: `pipeline/scheduler.py` — Background Scheduler

**Files:**
- Create: `pipeline/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheduler.py`:

```python
"""Tests for pipeline/scheduler.py refresh logic."""
from unittest.mock import MagicMock, call, patch

import pytest


def test_refresh_all_tickers_calls_get_ticker_data_for_all_four():
    mock_data = {"df": MagicMock()}
    with patch("pipeline.scheduler.get_ticker_data", return_value=mock_data) as mock_get, \
         patch("pipeline.scheduler.write_cache") as mock_write:
        from pipeline.scheduler import refresh_all_tickers, DEFAULT_PERIOD, DEFAULT_N_STATES
        refresh_all_tickers()
        assert mock_get.call_count == 4
        assert mock_write.call_count == 4


def test_refresh_all_tickers_uses_default_params():
    mock_data = {"df": MagicMock()}
    with patch("pipeline.scheduler.get_ticker_data", return_value=mock_data) as mock_get, \
         patch("pipeline.scheduler.write_cache"):
        from pipeline.scheduler import refresh_all_tickers, DEFAULT_PERIOD, DEFAULT_N_STATES
        refresh_all_tickers()
        for c in mock_get.call_args_list:
            assert c.kwargs.get("period", c.args[1] if len(c.args) > 1 else None) == DEFAULT_PERIOD
            assert c.kwargs.get("n_states", c.args[2] if len(c.args) > 2 else None) == DEFAULT_N_STATES


def test_refresh_all_tickers_continues_after_single_failure():
    call_count = 0

    def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("yfinance timeout")
        return {"df": MagicMock()}

    with patch("pipeline.scheduler.get_ticker_data", side_effect=flaky), \
         patch("pipeline.scheduler.write_cache"):
        from pipeline.scheduler import refresh_all_tickers
        refresh_all_tickers()  # must not raise
    assert call_count == 4  # all 4 attempted despite error on ticker 2


def test_warm_stale_tickers_skips_fresh_cache():
    with patch("pipeline.scheduler.read_cache", return_value={"df": MagicMock()}) as mock_read, \
         patch("pipeline.scheduler.get_ticker_data") as mock_get, \
         patch("pipeline.scheduler.write_cache"):
        from pipeline.scheduler import _warm_stale_tickers
        _warm_stale_tickers()
        mock_get.assert_not_called()


def test_warm_stale_tickers_refreshes_missing_cache():
    with patch("pipeline.scheduler.read_cache", return_value=None), \
         patch("pipeline.scheduler.get_ticker_data", return_value={"df": MagicMock()}) as mock_get, \
         patch("pipeline.scheduler.write_cache"):
        from pipeline.scheduler import _warm_stale_tickers
        _warm_stale_tickers()
        assert mock_get.call_count == 4
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_scheduler.py -v
```
Expected: `ModuleNotFoundError` — `pipeline/scheduler.py` doesn't exist yet.

- [ ] **Step 3: Implement `pipeline/scheduler.py`**

```python
"""
pipeline/scheduler.py
──────────────────────
Background scheduler that pre-computes all 4 tickers every 60 minutes.

Use create_scheduler() via st.cache_resource for a process-level singleton.

Public API
──────────
  create_scheduler()       → BackgroundScheduler (call via st.cache_resource)
  refresh_all_tickers()    → None (also callable directly for testing)
  DEFAULT_PERIOD           — "730d"
  DEFAULT_N_STATES         — 6
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from pipeline.cache import read_cache, write_cache
from pipeline.download import TICKERS
from strategy.signals import get_ticker_data

DEFAULT_PERIOD   = "730d"
DEFAULT_N_STATES = 6

logger = logging.getLogger(__name__)


def refresh_all_tickers() -> None:
    """Run the full pipeline for all 4 tickers and write results to disk cache."""
    logger.info("Scheduler: starting hourly refresh")
    for ticker in TICKERS:
        try:
            data = get_ticker_data(
                ticker   = ticker,
                period   = DEFAULT_PERIOD,
                n_states = DEFAULT_N_STATES,
            )
            write_cache(ticker, DEFAULT_PERIOD, DEFAULT_N_STATES, data)
            logger.info("Scheduler: refreshed %s", ticker)
        except Exception as exc:
            logger.error("Scheduler: failed to refresh %s — %s", ticker, exc)
    logger.info("Scheduler: refresh complete")


def _warm_stale_tickers() -> None:
    """On startup, immediately compute any ticker whose cache is missing or stale."""
    for ticker in TICKERS:
        if read_cache(ticker, DEFAULT_PERIOD, DEFAULT_N_STATES) is None:
            logger.info("Scheduler: warming cold cache for %s", ticker)
            try:
                data = get_ticker_data(
                    ticker   = ticker,
                    period   = DEFAULT_PERIOD,
                    n_states = DEFAULT_N_STATES,
                )
                write_cache(ticker, DEFAULT_PERIOD, DEFAULT_N_STATES, data)
            except Exception as exc:
                logger.error("Scheduler: warm failed for %s — %s", ticker, exc)


def create_scheduler() -> BackgroundScheduler:
    """
    Warm stale caches, then start the background scheduler.
    Must be called via @st.cache_resource to ensure one instance per process.
    """
    _warm_stale_tickers()
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_all_tickers, "interval", minutes=60)
    scheduler.start()
    logger.info("Scheduler: started — interval=60min")
    return scheduler
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_scheduler.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/scheduler.py tests/test_scheduler.py
git commit -m "feat: add background scheduler for hourly cache pre-computation"
```

---

## Task 4: Update `app/dashboard.py` — Wire Cache into Loader

**Files:**
- Modify: `app/dashboard.py` (imports section + `load_ticker` function + add scheduler call)

- [ ] **Step 1: Add imports at the top of `app/dashboard.py`**

After the existing imports block (around line 36), add:

```python
from pipeline.cache     import read_cache, write_cache, get_last_refreshed
from pipeline.scheduler import create_scheduler, DEFAULT_PERIOD, DEFAULT_N_STATES
```

- [ ] **Step 2: Add scheduler singleton call after the theme state block**

After the theme state block (around line 55, after the `st.markdown(LIGHT_MODE_CSS ...)` conditional), add:

```python
# Start background scheduler — process-level singleton via st.cache_resource
@st.cache_resource
def _start_scheduler():
    return create_scheduler()

_start_scheduler()
```

- [ ] **Step 3: Replace `load_ticker()` to use disk cache**

Replace the existing `load_ticker` function (lines 136–139) with:

```python
@st.cache_data(ttl=4200, show_spinner=False)
def load_ticker(ticker: str, period: str, n_states: int) -> dict:
    """Load full pipeline: disk cache first, live compute fallback."""
    cached = read_cache(ticker, period, n_states)
    if cached is not None:
        return cached
    with st.spinner(f"Loading {ticker} — first run, this takes ~30s…"):
        data = get_ticker_data(ticker=ticker, period=period, n_states=n_states)
        write_cache(ticker, period, n_states, data)
        return data
```

Note: `st.cache_data` TTL is set to 70 minutes (4200s) to match the disk cache TTL, preventing a stale in-memory entry from bypassing a fresh disk write.

- [ ] **Step 4: Add "Data as of" label in the dashboard**

Find the section in `dashboard.py` where the selected ticker's data is first displayed (the hero signal banner area). Add a small freshness label:

```python
last_refreshed = get_last_refreshed(selected_ticker)
if last_refreshed:
    st.caption(f"Data as of {last_refreshed}")
```

- [ ] **Step 5: Run existing tests to confirm nothing is broken**

```bash
pytest tests/ -v --ignore=tests/test_imports.py
```
Expected: all previously passing tests still PASS. (test_imports.py is excluded as it does a live import that may try to connect to yfinance.)

- [ ] **Step 6: Commit**

```bash
git add app/dashboard.py
git commit -m "feat: wire disk cache and background scheduler into dashboard loader"
```

---

## Task 5: Update `requirements.txt`

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add APScheduler**

Add to `requirements.txt`:

```
apscheduler>=3.10.0,<4.0.0
```

- [ ] **Step 2: Verify the full requirements list looks correct**

```bash
cat requirements.txt
```
Expected output:
```
# Regime-Based Trading App
streamlit>=1.35.0
plotly>=5.20.0
yfinance>=0.2.40
hmmlearn>=0.3.0
scikit-learn>=1.3.0
numpy>=1.26.0
pandas>=2.0.0
apscheduler>=3.10.0,<4.0.0
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add apscheduler dependency"
```

---

## Task 6: Manual Infrastructure Steps (Railway Volume + Cloudflare)

These are configuration steps outside the codebase. Complete them after deploying the code changes.

### Railway Persistent Volume

- [ ] **Step 1: Create Railway volume**
  - Open Railway dashboard → your project → the btgtraders service → **Volumes** tab
  - Click **+ New Volume**
  - Mount path: `/data`
  - Save and redeploy

- [ ] **Step 2: Verify volume is mounted**
  - After redeploy, check Railway logs for: `Scheduler: warming cold cache for BTC-USD` (and other tickers)
  - This confirms the scheduler started and is writing to `/data/cache/`

### Cloudflare DNS Proxy

- [ ] **Step 3: Add site to Cloudflare**
  - Go to dash.cloudflare.com → **Add a Site** → enter `btgtraders.com` → select **Free** plan

- [ ] **Step 4: Update Namecheap nameservers**
  - Cloudflare will display two nameservers (e.g. `ada.ns.cloudflare.com`)
  - In Namecheap → Domain List → btgtraders.com → **Nameservers** → Custom DNS → paste both Cloudflare nameservers
  - DNS propagation takes 5–30 minutes

- [ ] **Step 5: Add DNS record in Cloudflare**
  - In Cloudflare DNS tab: **Add record**
  - Type: `CNAME`, Name: `btgtraders.com` (or `@`), Target: your Railway public domain (e.g. `web-production-1e655.up.railway.app`), Proxy: **enabled (orange cloud)**
  - Cloudflare's CNAME Flattening handles the apex domain automatically — do not add an A record

- [ ] **Step 6: Set SSL mode to Full**
  - Cloudflare → SSL/TLS → Overview → set to **Full** (not Flexible)
  - Flexible would cause a redirect loop since Railway already serves HTTPS

- [ ] **Step 7: Verify Cloudflare is proxying**
  ```bash
  dig btgtraders.com
  ```
  Expected: answer section shows Cloudflare IP addresses (starting with `104.x.x.x` or `172.x.x.x`), not Railway's IP.

---

## Task 7: Full Regression + Deploy

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 2: Push to GitHub (triggers Railway redeploy)**

```bash
git push origin main
```

- [ ] **Step 3: Monitor Railway logs for scheduler startup**

In Railway dashboard → Logs, confirm within 2 minutes of deploy:
```
Scheduler: warming cold cache for BTC-USD
Scheduler: warming cold cache for ETH-USD
Scheduler: warming cold cache for SOL-USD
Scheduler: warming cold cache for ADA-USD
Scheduler: started — interval=60min
```

- [ ] **Step 4: Verify load time**

Visit btgtraders.com — page should load within 2 seconds (after the initial warm-up completes on first deploy).
