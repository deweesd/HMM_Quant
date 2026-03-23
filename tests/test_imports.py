"""Smoke tests — verify every module can be imported without error."""

def test_pipeline_download_imports():
    from pipeline.download import download_ohlcv, TICKERS, TICKER_LABELS
    from pipeline.download import REQUIRED_COLS, PERIOD, INTERVAL
    assert len(TICKERS) == 4

def test_pipeline_features_imports():
    from pipeline.features import engineer_features, robust_clip, FEATURE_COLS
    assert FEATURE_COLS == ["Returns", "Range", "Vol_Change"]

def test_pipeline_indicators_imports():
    from pipeline.indicators import add_indicators, compute_adx

def test_models_hmm_imports():
    from models.hmm import fit_hmm, N_STATES, RANDOM_SEED
    assert N_STATES == 6

def test_strategy_signals_imports():
    from strategy.signals import score_signals, get_ticker_data
    from strategy.signals import CONFIRM_COLS, CONFIRM_LABELS
    assert len(CONFIRM_COLS) == 10

def test_strategy_backtest_imports():
    from strategy.backtest import run_backtest
