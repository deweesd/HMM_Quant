"""
////// data_prep.py \\\\\\
──────────────────────────────────────────────────────────────────────────────
Full data pipeline for the Regime-Based Trading App.

Steps
─────
  1. Download hourly OHLCV via yfinance (730d, 1h interval)
  2. Flatten MultiIndex columns → Open / High / Low / Close / Volume
  3. Engineer HMM training features: Returns, Range, Vol_Change
  4. IQR-based outlier clipping (prevents degenerate HMM covariance matrices)
  5. Compute 10 technical indicators: EMA20, EMA200, RSI, MACD, ADX,
     Vol_SMA20, Momentum, Volatility (+ MACD_Signal, MACD_Hist)
  6. Fit 6-state GaussianHMM on StandardScaler-normalised features
  7. Auto-label Bull (max mean return) and Bear (min mean return) states;
     all remaining states are labelled Neutral
  8. Score the 10 confirmation signals → Confirmations (int 0-10)
  9. Generate trade signal: LONG / SHORT / NEUTRAL

Public API
──────────
  get_ticker_data(ticker, period, interval, n_states) → dict
    Keys: df, bull_state_id, bear_state_id, state_summary

  TICKERS        — list of 4 ticker strings
  TICKER_LABELS  — {ticker: short_name}
  CONFIRM_LABELS — {col_name: human_readable_label}
  N_STATES       — default HMM state count (6)
"""

import warnings
import numpy  as np
import pandas as pd
import yfinance as yf
from hmmlearn.hmm          import GaussianHMM
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ── Constants ──────────────────────────────────────────────────────────────────
TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD"]
TICKER_LABELS = {
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
    "SOL-USD": "SOL",
    "ADA-USD": "ADA",
}
PERIOD    = "730d"
INTERVAL  = "1h"
N_STATES  = 6
RANDOM_SEED = 42

REQUIRED_COLS = ["Open", "High", "Low", "Close", "Volume"]
FEATURE_COLS  = ["Returns", "Range", "Vol_Change"]

# Column names for the 10 confirmation signals
CONFIRM_COLS = [
    "C1_RSI_lt_80",
    "C2_Mom_gt_1p5",
    "C3_Vol_lt_6",
    "C4_MACD_near_pos",
    "C5_Vol_gt_SMA",
    "C6_ADX_gt_30",
    "C7_Price_gt_EMA20",
    "C8_Price_gt_EMA200",
    "C9_MACD_gt_Signal",
    "C10_RSI_gt_20",
]

# Human-readable labels shown in the dashboard
CONFIRM_LABELS = {
    "C1_RSI_lt_80":       "RSI < 80  (not overbought)",
    "C2_Mom_gt_1p5":      "Momentum > 1.5%  (24-hr)",
    "C3_Vol_lt_6":        "Volatility < 6%  (24-hr realised)",
    "C4_MACD_near_pos":   "MACD nearing positive (histogram > -0.1% of price)",
    "C5_Vol_gt_SMA":      "Volume > 20-bar SMA",
    "C6_ADX_gt_30":       "ADX > 30  (strong trend)",
    "C7_Price_gt_EMA20":  "Price > EMA 20",
    "C8_Price_gt_EMA200": "Price > EMA 200",
    "C9_MACD_gt_Signal":  "MACD > Signal line  (bullish cross)",
    "C10_RSI_gt_20":      "RSI > 20  (not deeply oversold)",
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Download & flatten OHLCV
# ══════════════════════════════════════════════════════════════════════════════

def _download(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """
    Download OHLCV from yfinance and return a flat DataFrame with exactly
    Open / High / Low / Close / Volume columns.

    yfinance ≥ 0.2.38 returns a MultiIndex even for single-ticker downloads:
      Level 0 → field name  (Open, High, Low, Close, Volume)
      Level 1 → ticker      (BTC-USD, …)
    We flatten using get_level_values(0) to recover the field names.
    """
    raw = yf.download(
        ticker,
        period      = period,
        interval    = interval,
        auto_adjust = True,
        progress    = False,
        prepost     = False,
    )

    if raw.empty:
        raise ValueError(
            f"yfinance returned no data for {ticker}. "
            "Check internet connection or try a smaller period."
        )

    # Flatten MultiIndex → field names at level 0
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Drop any duplicate columns that yfinance may inject
    raw = raw.loc[:, ~raw.columns.duplicated()]

    # Verify all required columns are present
    missing = [c for c in REQUIRED_COLS if c not in raw.columns]
    if missing:
        raise KeyError(
            f"{ticker}: columns {missing} missing after MultiIndex flatten. "
            f"Available: {raw.columns.tolist()}"
        )

    df = raw[REQUIRED_COLS].dropna(how="all").sort_index()
    return df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Feature engineering for HMM training
# ══════════════════════════════════════════════════════════════════════════════

def _robust_clip(series: pd.Series, mult: float) -> pd.Series:
    """Clip to [Q25 - mult×IQR, Q75 + mult×IQR]. Scale-invariant outlier removal."""
    q25, q75 = series.quantile(0.25), series.quantile(0.75)
    iqr = q75 - q25
    if iqr == 0:
        return series
    return series.clip(q25 - mult * iqr, q75 + mult * iqr)


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the three HMM training features from OHLCV data.

      Returns    = Close.pct_change()             — momentum / direction
      Range      = (High - Low) / Close           — intrabar volatility
      Vol_Change = Volume.pct_change()            — liquidity shift

    Cleaning pipeline:
      A) dropna()         — removes the first pct_change row
      B) replace ±inf     — Volume=0 in prior bar → Vol_Change = ±inf
      C) dropna() again   — removes newly NaN rows from step B
      D) IQR clip         — removes extreme outliers that hijack HMM states
    """
    out = df.copy()
    out["Returns"]    = out["Close"].pct_change()
    out["Range"]      = (out["High"] - out["Low"]) / out["Close"]
    out["Vol_Change"] = out["Volume"].pct_change()

    out = out.dropna(subset=FEATURE_COLS)
    out[FEATURE_COLS] = out[FEATURE_COLS].replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=FEATURE_COLS)

    # Conservative IQR multipliers — clip data artefacts, keep real moves
    out["Returns"]    = _robust_clip(out["Returns"],    mult=10.0)
    out["Range"]      = _robust_clip(out["Range"],      mult=10.0)
    out["Vol_Change"] = _robust_clip(out["Vol_Change"], mult=5.0)

    return out


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Technical indicators (all 10 confirmations)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder-smoothed Average Directional Index (ADX).

    Uses alpha = 1/period (Wilder smoothing), NOT pandas ewm(span=period)
    which uses alpha = 2/(period+1).  The difference matters — Wilder ADX
    is considerably smoother and matches TradingView / most TA libraries.
    """
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]
    alpha = 1.0 / period

    # True Range
    tr = pd.concat(
        [high - low,
         (high - close.shift(1)).abs(),
         (low  - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)

    # Directional Movement
    up   = high - high.shift(1)
    down = low.shift(1) - low

    plus_dm  = up.where(  (up > down) & (up > 0),   0.0)
    minus_dm = down.where((down > up) & (down > 0),  0.0)

    # Wilder smoothing
    atr      = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm( alpha=alpha, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr

    # DX → ADX
    denom = (plus_di + minus_di).replace(0, np.nan)
    dx    = 100 * (plus_di - minus_di).abs() / denom
    adx   = dx.ewm(alpha=alpha, adjust=False).mean()
    return adx


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all technical indicators needed for the 10-confirmation signal.

    Indicators added
    ────────────────
    EMA20, EMA200      — trend baseline
    RSI                — 14-period Wilder RSI
    MACD               — 12/26 EMA difference
    MACD_Signal        — 9-period EMA of MACD
    MACD_Hist          — MACD − MACD_Signal
    ADX                — 14-period Wilder ADX
    Vol_SMA20          — 20-bar simple volume average
    Momentum           — 24-hour price return (%)
    Volatility         — 24-bar rolling std of Returns × sqrt(24) (%)
    """
    out = df.copy()

    # EMA
    out["EMA20"]  = out["Close"].ewm(span=20,  adjust=False).mean()
    out["EMA200"] = out["Close"].ewm(span=200, adjust=False).mean()

    # RSI (14-period, Wilder smoothing)
    alpha_rsi = 1.0 / 14
    delta     = out["Close"].diff()
    gain      = delta.clip(lower=0)
    loss      = (-delta.clip(upper=0))
    avg_gain  = gain.ewm(alpha=alpha_rsi, adjust=False).mean()
    avg_loss  = loss.ewm(alpha=alpha_rsi, adjust=False).mean()
    rs        = avg_gain / (avg_loss + 1e-10)
    out["RSI"] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12          = out["Close"].ewm(span=12, adjust=False).mean()
    ema26          = out["Close"].ewm(span=26, adjust=False).mean()
    out["MACD"]         = ema12 - ema26
    out["MACD_Signal"]  = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_Hist"]    = out["MACD"] - out["MACD_Signal"]

    # ADX
    out["ADX"] = _compute_adx(out, period=14)

    # Volume SMA
    out["Vol_SMA20"] = out["Volume"].rolling(20).mean()

    # Momentum: 24-hour price return in %
    # Using 24-bar look-back so the 1.5% threshold is meaningful
    out["Momentum"] = (out["Close"] / out["Close"].shift(24) - 1) * 100

    # Volatility: 24-bar rolling realised vol (annualised to daily %)
    # sqrt(24) converts hourly std to a daily-equivalent figure
    out["Volatility"] = out["Returns"].rolling(24).std() * np.sqrt(24) * 100

    return out


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Fit GaussianHMM and label regimes
# ══════════════════════════════════════════════════════════════════════════════

def _fit_hmm(df: pd.DataFrame, n_states: int, random_state: int):
    """
    Fit a 6-state GaussianHMM on the three scaled features.

    Returns
    ───────
    df_out        — input df with 'HMM_State' and 'Regime' columns added
    bull_state_id — int, state with highest inverse-transformed mean return
    bear_state_id — int, state with lowest  inverse-transformed mean return
    state_summary — pd.DataFrame with one row per state
    model         — fitted GaussianHMM
    scaler        — fitted StandardScaler

    PITFALL — scaled vs original means
    ───────────────────────────────────
    model.means_ lives in StandardScaler space.  We inverse-transform before
    comparing so that Bull/Bear labels reflect actual returns, not scaled values
    (though for argmax/argmin the ordering is the same — we inverse-transform
    anyway so we can display real return values in the summary table).
    """
    X_raw    = df[FEATURE_COLS].values
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    model = GaussianHMM(
        n_components    = n_states,
        covariance_type = "full",
        n_iter          = 1000,
        random_state    = random_state,
        tol             = 1e-4,
        verbose         = False,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X_scaled)

    states = model.predict(X_scaled)

    # Inverse-transform means to get interpretable return values
    means_orig   = scaler.inverse_transform(model.means_)   # shape (n_states, 3)
    return_means = means_orig[:, 0]                          # index 0 = Returns

    bull_state_id = int(np.argmax(return_means))
    bear_state_id = int(np.argmin(return_means))

    # Ensure they're distinct (degenerate edge case on flat data)
    if bull_state_id == bear_state_id:
        sorted_ids    = np.argsort(return_means)
        bear_state_id = int(sorted_ids[0])
        bull_state_id = int(sorted_ids[-1])

    def _label(s: int) -> str:
        if s == bull_state_id:
            return "Bull"
        if s == bear_state_id:
            return "Bear"
        return "Neutral"

    df_out = df.copy()
    df_out["HMM_State"] = states
    df_out["Regime"]    = df_out["HMM_State"].map(_label)

    # Build per-state summary table
    rows = []
    for s in range(n_states):
        mask = df_out["HMM_State"] == s
        rows.append({
            "State":       s,
            "Label":       _label(s),
            "Mean_Return": round(float(df_out.loc[mask, "Returns"].mean()), 6),
            "Volatility":  round(float(df_out.loc[mask, "Returns"].std()),  6),
            "Count":       int(mask.sum()),
            "Avg_Range":   round(float(df_out.loc[mask, "Range"].mean()),   6),
        })
    state_summary = (
        pd.DataFrame(rows)
        .sort_values("Mean_Return", ascending=False)
        .reset_index(drop=True)
    )

    return df_out, bull_state_id, bear_state_id, state_summary, model, scaler


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Score the 10 confirmation signals
# ══════════════════════════════════════════════════════════════════════════════

def _score_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute each of the 10 boolean confirmations and sum them into
    'Confirmations'.  Then assign the final trade signal:

      LONG    — Regime == 'Bull'  AND  Confirmations >= 8
      SHORT   — Regime == 'Bear'  (display label; we don't short in backtest)
      NEUTRAL — everything else
    """
    out = df.copy()

    # ── 10 confirmations ──────────────────────────────────────────────────────
    # C1: RSI not overbought
    out["C1_RSI_lt_80"]       = out["RSI"] < 80

    # C2: 24-hour momentum positive and meaningful
    out["C2_Mom_gt_1p5"]      = out["Momentum"] > 1.5

    # C3: 24-bar realised volatility below 6% — calmer conditions
    out["C3_Vol_lt_6"]        = out["Volatility"] < 6.0

    # C4: MACD histogram is within 0.1% of close from being positive
    #     (i.e. MACD is "nearing" positive, not deep in negative territory)
    out["C4_MACD_near_pos"]   = out["MACD_Hist"] > -(out["Close"] * 0.001)

    # C5: Current volume exceeds its 20-bar average (liquidity confirmation)
    out["C5_Vol_gt_SMA"]      = out["Volume"] > out["Vol_SMA20"]

    # C6: Strong trend — ADX above 30
    out["C6_ADX_gt_30"]       = out["ADX"] > 30

    # C7 / C8: Price above short and long-term moving averages
    out["C7_Price_gt_EMA20"]  = out["Close"] > out["EMA20"]
    out["C8_Price_gt_EMA200"] = out["Close"] > out["EMA200"]

    # C9: MACD line above signal line (bullish crossover)
    out["C9_MACD_gt_Signal"]  = out["MACD"] > out["MACD_Signal"]

    # C10: RSI not deeply oversold (not panic territory)
    out["C10_RSI_gt_20"]      = out["RSI"] > 20

    # ── Sum confirmations (treat NaN booleans as False) ───────────────────────
    out["Confirmations"] = out[CONFIRM_COLS].fillna(False).astype(int).sum(axis=1)

    # ── Trade signal ──────────────────────────────────────────────────────────
    conditions = [
        (out["Regime"] == "Bull") & (out["Confirmations"] >= 8),
        out["Regime"] == "Bear",
    ]
    choices = ["LONG", "SHORT"]
    out["Signal"] = np.select(conditions, choices, default="NEUTRAL")

    return out


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def get_ticker_data(
    ticker:    str  = "BTC-USD",
    period:    str  = PERIOD,
    interval:  str  = INTERVAL,
    n_states:  int  = N_STATES,
    rand_seed: int  = RANDOM_SEED,
) -> dict:
    """
    Full pipeline: download → features → indicators → HMM → signals.

    Returns a dict with:
      'df'            — complete DataFrame with all features, indicators,
                        HMM_State, Regime, Confirmations, Signal
      'bull_state_id' — int  (HMM state labelled Bull)
      'bear_state_id' — int  (HMM state labelled Bear)
      'state_summary' — pd.DataFrame  (one row per state, sorted by mean return)
      'ticker'        — str
    """
    # 1. Download
    raw = _download(ticker, period, interval)

    # 2. HMM features
    df = _engineer_features(raw)

    # 3. Technical indicators
    df = _add_indicators(df)

    # 4. Drop rows with NaN indicators (EMA200 warm-up, ADX warm-up, etc.)
    indicator_cols = [
        "EMA20", "EMA200", "RSI", "MACD", "MACD_Signal",
        "ADX", "Vol_SMA20", "Momentum", "Volatility",
    ]
    df = df.dropna(subset=indicator_cols).copy()

    # 5. Fit HMM
    df, bull_id, bear_id, summary, model, scaler = _fit_hmm(
        df, n_states=n_states, random_state=rand_seed
    )

    # 6. Score confirmations
    df = _score_signals(df)

    return {
        "df":            df,
        "bull_state_id": bull_id,
        "bear_state_id": bear_id,
        "state_summary": summary,
        "ticker":        ticker,
    }
