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
from typing import Optional

TTL_MINUTES = 70
_MANIFEST_FILENAME = "manifest.json"

logger = logging.getLogger(__name__)


def _ensure_dir() -> None:
    os.makedirs(os.environ.get("CACHE_DIR", "/data/cache"), exist_ok=True)


def _cache_path(ticker: str, period: str, n_states: int) -> str:
    return os.path.join(os.environ.get("CACHE_DIR", "/data/cache"), f"{ticker}_{period}_{n_states}.pkl")


def _manifest_path() -> str:
    return os.path.join(os.environ.get("CACHE_DIR", "/data/cache"), _MANIFEST_FILENAME)


def write_cache(ticker: str, period: str, n_states: int, data: dict) -> None:
    """Pickle data to disk and update the manifest timestamp."""
    _ensure_dir()
    path = _cache_path(ticker, period, n_states)
    with open(path, "wb") as f:
        pickle.dump(data, f)
    _update_manifest(ticker)
    logger.info("Cache written: %s", path)


def read_cache(ticker: str, period: str, n_states: int) -> Optional[dict]:
    """Return cached data if present and within TTL, else None."""
    path = _cache_path(ticker, period, n_states)
    if not os.path.exists(path):
        return None
    age_minutes = (datetime.now(timezone.utc).timestamp() - os.path.getmtime(path)) / 60
    if age_minutes > TTL_MINUTES:
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        logger.warning("Cache file corrupt or unreadable: %s", path)
        return None


def get_last_refreshed(ticker: str) -> Optional[str]:
    """Return 'HH:MM UTC' string of last refresh for ticker, or None."""
    mpath = _manifest_path()
    if not os.path.exists(mpath):
        return None
    with open(mpath) as f:
        manifest = json.load(f)
    return manifest.get(ticker)


def _update_manifest(ticker: str) -> None:
    import tempfile
    mpath = _manifest_path()
    manifest: dict = {}
    if os.path.exists(mpath):
        try:
            with open(mpath) as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}
    manifest[ticker] = datetime.now(timezone.utc).strftime("%H:%M UTC")
    dir_ = os.path.dirname(mpath)
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp") as tmp:
        json.dump(manifest, tmp)
        tmp_path = tmp.name
    os.replace(tmp_path, mpath)
