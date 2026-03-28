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
