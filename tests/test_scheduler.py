"""Tests for pipeline/scheduler.py refresh logic."""
from unittest.mock import MagicMock, patch

import pytest

from pipeline.scheduler import (
    DEFAULT_N_STATES,
    DEFAULT_PERIOD,
    _warm_stale_tickers,
    refresh_all_tickers,
)


def test_refresh_all_tickers_calls_get_ticker_data_for_all_four():
    mock_data = {"df": MagicMock()}
    with patch("pipeline.scheduler.get_ticker_data", return_value=mock_data) as mock_get, \
         patch("pipeline.scheduler.write_cache") as mock_write:
        refresh_all_tickers()
        assert mock_get.call_count == 4
        assert mock_write.call_count == 4


def test_refresh_all_tickers_uses_default_params():
    mock_data = {"df": MagicMock()}
    with patch("pipeline.scheduler.get_ticker_data", return_value=mock_data) as mock_get, \
         patch("pipeline.scheduler.write_cache"):
        refresh_all_tickers()
        for c in mock_get.call_args_list:
            assert c.kwargs["period"] == DEFAULT_PERIOD
            assert c.kwargs["n_states"] == DEFAULT_N_STATES


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
        refresh_all_tickers()  # must not raise
    assert call_count == 4


def test_warm_stale_tickers_skips_fresh_cache():
    with patch("pipeline.scheduler.read_cache", return_value={"df": MagicMock()}), \
         patch("pipeline.scheduler.get_ticker_data") as mock_get, \
         patch("pipeline.scheduler.write_cache"):
        _warm_stale_tickers()
        mock_get.assert_not_called()


def test_warm_stale_tickers_refreshes_missing_cache():
    with patch("pipeline.scheduler.read_cache", return_value=None), \
         patch("pipeline.scheduler.get_ticker_data", return_value={"df": MagicMock()}) as mock_get, \
         patch("pipeline.scheduler.write_cache"):
        _warm_stale_tickers()
        assert mock_get.call_count == 4


def test_warm_stale_tickers_continues_after_failure():
    call_count = 0

    def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("warmup error")
        return {"df": MagicMock()}

    with patch("pipeline.scheduler.read_cache", return_value=None), \
         patch("pipeline.scheduler.get_ticker_data", side_effect=flaky), \
         patch("pipeline.scheduler.write_cache"):
        _warm_stale_tickers()  # must not raise
    assert call_count == 4
