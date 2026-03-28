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
