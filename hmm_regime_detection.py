# =============================================================================
# Market Regime Detection — BTC, ETH, SOL, ADA
# Hidden Markov Model (GaussianHMM) on Hourly Crypto Data
#
# Compatible with: Google Colab · Jupyter Notebook · Python 3.8+
# Run as a notebook by opening in Jupyter/Colab (cells separated by # %%)
# Run as a plain script:  python hmm_regime_detection.py
# =============================================================================


# %% [markdown]
# ## Market Regime Detection with Hidden Markov Models
# Detects 7 latent market regimes per cryptocurrency using hourly OHLCV features.
# Regimes are inferred from: Returns (momentum), Range (intrabar volatility),
# and Vol_Change (liquidity shifts). A GaussianHMM with full covariance is fitted
# independently per ticker so each asset's regime structure is learned separately.


# %%
# ////// CELL 1: Install Libraries \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# Run this cell first. If packages are already installed the pip call is a
# fast no-op. Pinning hmmlearn avoids breaking API changes between 0.2.x/0.3.x.
# ─────────────────────────────────────────────────────────────────────────────

# Install all required libraries (safe to re-run — pip skips already-installed packages)
# subprocess works in plain .py scripts, Jupyter, AND Google Colab
import subprocess, sys
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "-q",
    "yfinance", "hmmlearn", "matplotlib", "pandas", "numpy", "scikit-learn"
])


# %%
# ////// CELL 2: Imports & Global Settings \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# Standard data-science stack plus hmmlearn for the Hidden Markov Model and
# StandardScaler for feature normalisation (mandatory before GaussianHMM —
# see PITFALL notes in Cell 5).
# ─────────────────────────────────────────────────────────────────────────────

import warnings
import sys

import numpy  as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import yfinance as yf

from hmmlearn.hmm          import GaussianHMM
from sklearn.preprocessing import StandardScaler

# ── Suppress non-actionable warnings that clutter notebook output ─────────────
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*ConvergenceWarning.*")

# ── Notebook / terminal display helper ───────────────────────────────────────
# display() gives rich HTML tables in Jupyter/Colab; falls back to print() in
# plain script mode so the file runs without modification in both contexts.
try:
    from IPython.display import display as _display
    def show(df): _display(df)
except ImportError:
    def show(df): print(df.to_string(index=True))

# ── Matplotlib compatibility shim (colormaps API changed in 3.7) ──────────────
def get_cmap(name, n=None):
    """Return a colormap regardless of matplotlib version."""
    if hasattr(matplotlib, "colormaps"):          # matplotlib >= 3.7
        cmap = matplotlib.colormaps[name]
    else:
        cmap = plt.cm.get_cmap(name)              # matplotlib < 3.7
    return cmap

# ── Tickers and display names ─────────────────────────────────────────────────
TICKERS      = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD"]
TICKER_NAMES = ["BTC",     "ETH",     "SOL",     "ADA"]

N_STATES    = 7          # number of HMM hidden states (market regimes)
PLOT_HOURS  = 500        # how many trailing hours to show in the visual
RANDOM_SEED = 42

print(f"Python  {sys.version.split()[0]}  |  "
      f"pandas {pd.__version__}  |  "
      f"yfinance {yf.__version__}  |  "
      f"numpy {np.__version__}  |  "
      f"matplotlib {matplotlib.__version__}")


# %%
# ////// CELL 3: Download & Normalise OHLCV Data \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# Strategy
# ────────
# We call yf.download with period='730d' and interval='1h'.
#
# NOTE on the requested 1095-day window:
#   Yahoo Finance's API does NOT store more than ~730 calendar days of
#   intraday (hourly) history regardless of the period parameter passed.
#   Requesting '1095d' does not raise an error — yfinance silently truncates
#   the result to whatever Yahoo Finance will return (~730 days).
#   Using '730d' explicitly documents the true upper bound and avoids
#   confusion when the returned DataFrame is ~730 days, not 1095.
#   If Yahoo Finance later extends their retention window, simply change
#   the constant below.
#
# MultiIndex column handling
# ──────────────────────────
# yfinance ≥ 0.2.38 returns a MultiIndex even for single-ticker downloads:
#   Level 0  →  field name  (Open, High, Low, Close, Volume)
#   Level 1  →  ticker      (BTC-USD, …)
#
# We flatten using .get_level_values(0) which gives us the field names —
# NOT .get_level_values(1) which would give ticker strings and break all
# subsequent Open/High/Low/Close/Volume column references.
# ─────────────────────────────────────────────────────────────────────────────

PERIOD   = "730d"    # maximum reliable window for hourly yfinance data
INTERVAL = "1h"

REQUIRED_COLS = ["Open", "High", "Low", "Close", "Volume"]

def download_ohlcv(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """
    Download OHLCV data for a single ticker and return a clean flat DataFrame.

    Steps
    ─────
    1. yf.download with the given period / interval.
    2. Drop any MultiIndex by taking level-0 (field names).
    3. Verify all required columns are present.
    4. Drop rows where ALL price columns are NaN (exchange outages, gaps).
    5. Sort by datetime index.
    """
    # ── 1. Download ───────────────────────────────────────────────────────────
    raw = yf.download(
        ticker,
        period   = period,
        interval = interval,
        auto_adjust = True,   # adjust for splits/dividends
        progress    = False,
        prepost     = False,
    )

    if raw.empty:
        raise ValueError(
            f"yfinance returned no data for {ticker}. "
            "Check your internet connection or try a different period/interval."
        )

    # ── 2. Flatten MultiIndex columns (get_level_values(0) → field names) ─────
    if isinstance(raw.columns, pd.MultiIndex):
        # Level 0 = field ('Open','High','Low','Close','Volume')
        # Level 1 = ticker ('BTC-USD' …)
        # We want level 0 so the final columns are exactly Open/High/Low/Close/Volume
        raw.columns = raw.columns.get_level_values(0)

    # After flattening, duplicate column names can appear if yfinance injected
    # extra metadata columns — keep only the first occurrence of each name.
    raw = raw.loc[:, ~raw.columns.duplicated()]

    # ── 3. Verify required columns exist ──────────────────────────────────────
    missing = [c for c in REQUIRED_COLS if c not in raw.columns]
    if missing:
        raise KeyError(
            f"{ticker}: columns {missing} are missing after flattening. "
            f"Available columns: {raw.columns.tolist()}"
        )

    # ── 4. Keep only the 5 OHLCV columns, drop full-NaN rows ─────────────────
    df = raw[REQUIRED_COLS].dropna(how="all").sort_index()

    n_hours = len(df)
    n_days  = (df.index[-1] - df.index[0]).days
    print(f"  {ticker:<12} {n_hours:>6} hourly bars  "
          f"({n_days} calendar days  "
          f"{df.index[0].date()} → {df.index[-1].date()})")
    return df


print(f"\nDownloading hourly OHLCV  |  period='{PERIOD}'  interval='{INTERVAL}'\n")
raw_data: dict[str, pd.DataFrame] = {}
for ticker in TICKERS:
    raw_data[ticker] = download_ohlcv(ticker, PERIOD, INTERVAL)

print("\nDownload complete.\n")


# %%
# ////// CELL 4: Feature Engineering \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# We construct exactly three features per hourly bar:
#
#   Returns    = Close.pct_change()
#                Captures momentum / direction of price movement.
#
#   Range      = (High - Low) / Close
#                Intrabar volatility proxy — how much price oscillated
#                relative to closing price. Bounded below by 0.
#
#   Vol_Change = Volume.pct_change()
#                Captures liquidity surges and dries — large positive spikes
#                often accompany breakouts; negative spikes occur during
#                low-conviction consolidation.
#
# Cleaning pipeline
# ─────────────────
# Step A  dropna()       — removes first row (pct_change is NaN at t=0) and
#                          any rows where the feed had gaps.
# Step B  replace inf    — Volume of 0 in a prior bar makes Vol_Change = +inf;
#                          replace ±inf with NaN so they are removed cleanly.
# Step C  dropna() again — removes the rows newly tagged as NaN in step B.
#
# Outlier clipping  (critical before HMM fitting — see Cell 5 PITFALL note)
# ────────────────
# Crypto data contains genuine but extreme outliers: flash crashes, exchange
# reconnections after outages, and volume spikes of 1000× normal.
# Left unclipped, the HMM EM algorithm will dedicate one or more of the 7
# states entirely to capturing these outliers, wasting regime capacity.
#
# We clip using a robust IQR-based bound per feature per ticker:
#   lower = Q25 − multiplier × IQR
#   upper = Q75 + multiplier × IQR
#
# Multipliers chosen conservatively so we clip only genuine data errors while
# preserving legitimate extreme moves (e.g. BTC halving-day volume surges):
#   Returns    → IQR × 10   (lenient; flash crashes are real regime signal)
#   Range      → IQR × 10   (lenient; wide candles during news are real)
#   Vol_Change → IQR × 5    (stricter; 1000× volume spikes are data artefacts)
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_COLS = ["Returns", "Range", "Vol_Change"]

def robust_clip(series: pd.Series, iqr_mult: float) -> pd.Series:
    """Clip a series to [Q25 - mult*IQR, Q75 + mult*IQR]. Scale-invariant."""
    q25, q75 = series.quantile(0.25), series.quantile(0.75)
    iqr = q75 - q25
    if iqr == 0:
        return series   # constant series — clipping is meaningless
    return series.clip(q25 - iqr_mult * iqr, q75 + iqr_mult * iqr)


def engineer_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Compute Returns, Range, Vol_Change from an OHLCV DataFrame.
    Returns a clean, clipped feature DataFrame aligned to the same DatetimeIndex.
    """
    feat = df.copy()

    # ── Compute raw features ─────────────────────────────────────────────────
    feat["Returns"]    = feat["Close"].pct_change()
    feat["Range"]      = (feat["High"] - feat["Low"]) / feat["Close"]
    feat["Vol_Change"] = feat["Volume"].pct_change()

    # ── Step A: drop initial NaN row from pct_change ──────────────────────────
    feat = feat.dropna(subset=FEATURE_COLS)

    # ── Step B: replace ±inf (division by zero when prior Volume = 0) ─────────
    feat[FEATURE_COLS] = (
        feat[FEATURE_COLS]
        .replace([np.inf, -np.inf], np.nan)
    )

    # ── Step C: drop rows that became NaN in step B ───────────────────────────
    feat = feat.dropna(subset=FEATURE_COLS)

    # ── Outlier clipping ──────────────────────────────────────────────────────
    feat["Returns"]    = robust_clip(feat["Returns"],    iqr_mult=10.0)
    feat["Range"]      = robust_clip(feat["Range"],      iqr_mult=10.0)
    feat["Vol_Change"] = robust_clip(feat["Vol_Change"], iqr_mult=5.0)

    n_rows = len(feat)
    print(f"  {ticker:<12} {n_rows:>6} clean bars after feature engineering")
    return feat


print("Engineering features …\n")
feature_data: dict[str, pd.DataFrame] = {}
for ticker in TICKERS:
    feature_data[ticker] = engineer_features(raw_data[ticker], ticker)

print("\nFeature engineering complete.\n")


# %%
# ////// CELL 5: Train HMM Model \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# Model: hmmlearn.hmm.GaussianHMM
# ────────────────────────────────
# Each ticker gets its own independent model because:
#   • BTC and ADA have very different absolute volatility profiles.
#   • Shared transition probabilities would bias toward the most-traded asset.
#   • Independent models let each asset's regime structure be learnt from its
#     own distribution without contamination.
#
# Parameters
# ──────────
#   n_components    = 7    — 7 hidden states (market regimes)
#   covariance_type = 'full' — each state has its own 3×3 covariance matrix
#                              so the model can capture feature correlations
#                              inside each regime (e.g. high-vol + high-range
#                              tend to co-occur in panic states).
#   n_iter          = 1000 — max EM iterations; more than enough for convergence
#   random_state    = 42   — reproducible initialisation
#
# ⚠  PITFALL 1 — Unscaled features cause degenerate covariance matrices
# ────────────────────────────────────────────────────────────────────────
# GaussianHMM initialises using k-means on the raw feature matrix.
# If Vol_Change has variance ~10 000× that of Returns (common in crypto),
# the covariance matrices become numerically ill-conditioned, the log-
# likelihood hits -inf after the first EM step, and hmmlearn raises:
#   "ValueError: startprob_ must sum to 1.0"  or  NaN in the monitor log.
# FIX: StandardScaler (zero mean, unit variance) before fitting.
#      The scaler is stored so we can inverse-transform means for the
#      human-readable summary table.
#
# ⚠  PITFALL 2 — Outlier-dominated states
# ────────────────────────────────────────
# Without the clipping in Cell 4, a single 1000× volume spike can cause
# the HMM to dedicate one state to that single observation (a state with
# Count = 1 in the summary table). We pre-empted this with robust_clip().
# After fitting, check: if any state has Count < 30, the model may have
# overfit to noise — consider increasing the IQR multiplier in Cell 4.
#
# ⚠  PITFALL 3 — Non-convergence
# ────────────────────────────────
# 7-state full-covariance HMM has ~112 free parameters. With ~17 000 bars
# this is statistically fine, but EM can stall in a local optimum.
# We check model.monitor_.converged after fitting and warn if it did not.
# In that case: try a different random_state, reduce n_components, or
# switch covariance_type to 'diag' as a simpler fallback.
#
# ⚠  PITFALL 4 — State label instability across tickers
# ──────────────────────────────────────────────────────
# State 0 on BTC is NOT the same regime as State 0 on ETH — state indices
# are arbitrary artefacts of random initialisation. The summary table in
# Cell 6 sorts by Mean_Return so regimes are semantically comparable across
# tickers regardless of their raw integer label.
# ─────────────────────────────────────────────────────────────────────────────

def fit_hmm(feat_df: pd.DataFrame, ticker: str):
    """
    Fit GaussianHMM on the three engineered features and return:
        model      — fitted GaussianHMM
        feat_df    — input DataFrame with a new 'State' column appended
        scaler     — fitted StandardScaler (for inverse-transforming means)
    """
    X_raw = feat_df[FEATURE_COLS].values   # shape (T, 3)

    # ── Scale features to zero mean / unit variance ───────────────────────────
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    # ── Initialise model ──────────────────────────────────────────────────────
    model = GaussianHMM(
        n_components    = N_STATES,
        covariance_type = "full",
        n_iter          = 1000,
        random_state    = RANDOM_SEED,
        tol             = 1e-4,
        verbose         = False,
    )

    # ── Fit ───────────────────────────────────────────────────────────────────
    try:
        model.fit(X_scaled)
    except Exception as exc:
        raise RuntimeError(
            f"HMM fit failed for {ticker}: {exc}\n"
            "Tip: try increasing IQR clip multipliers in Cell 4, or "
            "reducing n_components."
        ) from exc

    # ── Convergence check ─────────────────────────────────────────────────────
    if not model.monitor_.converged:
        warnings.warn(
            f"[{ticker}] HMM did NOT fully converge in {model.n_iter} iterations. "
            "Regime assignments may be sub-optimal. "
            "Try: (a) increase n_iter, (b) reduce n_components, "
            "(c) switch covariance_type to 'diag'.",
            stacklevel=2,
        )

    # ── Predict hidden states ─────────────────────────────────────────────────
    hidden_states = model.predict(X_scaled)   # shape (T,)  values 0…6

    # Attach states back onto the DataFrame (in-place copy to avoid SettingWithCopy)
    out = feat_df.copy()
    out["State"] = hidden_states

    # ── Diagnostic: warn if any state has very few samples ────────────────────
    counts = pd.Series(hidden_states).value_counts()
    tiny   = counts[counts < 30]
    if not tiny.empty:
        warnings.warn(
            f"[{ticker}] States {tiny.index.tolist()} each have fewer than 30 "
            "observations — these may be outlier-capture states. "
            "Consider tightening the clip multipliers in Cell 4.",
            stacklevel=2,
        )

    log_score = model.score(X_scaled)
    print(f"  {ticker:<12} log-likelihood = {log_score:>14.2f}  "
          f"converged = {model.monitor_.converged}")

    return model, out, scaler


print("Fitting GaussianHMM (7 states, full covariance) …\n")
results: dict = {}   # keyed by ticker; stores model, feature df, scaler

for ticker in TICKERS:
    model, feat_with_states, scaler = fit_hmm(feature_data[ticker], ticker)
    results[ticker] = {
        "model":   model,
        "df":      feat_with_states,
        "scaler":  scaler,
    }

print("\nAll models fitted.\n")


# %%
# ////// CELL 6: Analyze — Summary Table \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# For each (ticker, state) pair we compute:
#
#   Mean_Return  — average hourly return in this regime
#                  Positive = bullish, negative = bearish, near-zero = ranging
#
#   Volatility   — std dev of returns in this regime
#                  High = turbulent / high-risk, low = calm / trend-following
#
#   Count        — number of hourly bars assigned to this regime
#                  Very low counts (<30) may indicate outlier-capture states
#                  (see PITFALL 2 in Cell 5)
#
# The table is sorted by Mean_Return descending so the most bullish regime
# appears at the top across all tickers.
#
# NOTE on state labels: the integer state IDs (0–6) are arbitrary and differ
# between tickers. Do not compare "State 3 of BTC" with "State 3 of ETH".
# Compare instead by the semantic labels derived from Mean_Return and Volatility.
# ─────────────────────────────────────────────────────────────────────────────

all_rows = []

for ticker in TICKERS:
    df_states = results[ticker]["df"]

    for state_id in range(N_STATES):
        mask   = df_states["State"] == state_id
        subset = df_states.loc[mask, "Returns"]

        all_rows.append({
            "Ticker":      ticker.replace("-USD", ""),
            "State":       int(state_id),
            "Mean_Return": subset.mean(),
            "Volatility":  subset.std(),
            "Count":       int(mask.sum()),
        })

summary_df = (
    pd.DataFrame(all_rows)
    .sort_values("Mean_Return", ascending=False)
    .reset_index(drop=True)
)

# Format percentage columns for readability
pd.set_option("display.float_format", "{:.6f}".format)
pd.set_option("display.max_rows", 40)

print("=" * 65)
print("  REGIME SUMMARY  (sorted by Mean_Return descending)")
print("=" * 65)
show(summary_df)
print()

# Highlight the top and bottom regimes per ticker for a quick sanity check
print("── Top regime per ticker (highest Mean_Return) ──────────────")
show(summary_df.groupby("Ticker").first().reset_index())

print("\n── Bottom regime per ticker (lowest Mean_Return) ────────────")
show(summary_df.groupby("Ticker").last().reset_index())


# %%
# ////// CELL 7: Visualize — Close Price + Regime Overlay \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# Layout: 2×2 grid, one subplot per cryptocurrency.
#
# Each subplot contains:
#   • A thin black line of Close price over the last PLOT_HOURS (500) hours.
#     This gives visual context for price levels and trends.
#   • A scatter overlay where each dot is coloured by its detected regime (0–6).
#     This is the "sanity check" — in a well-fitted model you should see:
#       - Coherent colour runs during trending periods (regime persistence)
#       - Colour changes around major price reversals or volatility spikes
#       - Not random salt-and-pepper colouring (which would suggest the model
#         failed to find meaningful structure)
#
# Colormap: 'tab10' (first 7 of 10 qualitatively distinct colours).
#   • Qualitative colormaps are required here — a sequential colormap like
#     viridis would make adjacent state IDs look similar, making it nearly
#     impossible to visually distinguish 7 regimes.
#   • tab10 colours are perceptually separated and print-safe.
#
# The legend shows all 7 regime colours with their integer state IDs.
# ─────────────────────────────────────────────────────────────────────────────

cmap   = get_cmap("tab10", N_STATES)
colors = [cmap(i / 10.0) for i in range(N_STATES)]  # tab10 has 10 slots; index by /10

fig, axes = plt.subplots(2, 2, figsize=(18, 11))
axes_flat = axes.flatten()

fig.suptitle(
    f"Market Regime Detection — Last {PLOT_HOURS} Hours\n"
    f"(7-State GaussianHMM  ·  Features: Returns, Intrabar Range, Volume Change)",
    fontsize=14,
    fontweight="bold",
    y=1.01,
)

for idx, ticker in enumerate(TICKERS):
    ax         = axes_flat[idx]
    df_states  = results[ticker]["df"]
    label_name = TICKER_NAMES[idx]

    # ── Slice the last PLOT_HOURS rows ─────────────────────────────────────────
    plot_df = df_states.tail(PLOT_HOURS).copy()

    # Close prices are in the feature DataFrame (retained from OHLCV)
    close_vals = plot_df["Close"].values
    times      = plot_df.index
    states     = plot_df["State"].values

    # ── Background line chart of Close price ──────────────────────────────────
    ax.plot(
        times, close_vals,
        color="black", linewidth=0.7, alpha=0.4, zorder=1,
        label="_nolegend_",
    )

    # ── Scatter overlay coloured by regime ────────────────────────────────────
    for state_id in range(N_STATES):
        mask = states == state_id
        if mask.sum() == 0:
            continue
        ax.scatter(
            times[mask],
            close_vals[mask],
            color  = colors[state_id],
            s      = 10,
            zorder = 2,
            alpha  = 0.85,
            label  = f"State {state_id}",
        )

    # ── Formatting ─────────────────────────────────────────────────────────────
    ax.set_title(f"{label_name}/USD", fontsize=13, fontweight="bold")
    ax.set_xlabel("Datetime (UTC)", fontsize=9)
    ax.set_ylabel("Close Price (USD)", fontsize=9)
    ax.tick_params(axis="x", labelsize=7, rotation=20)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(True, linewidth=0.4, alpha=0.4)

    # ── Per-subplot legend (state colours) ────────────────────────────────────
    handles = [
        mpatches.Patch(color=colors[s], label=f"Regime {s}")
        for s in range(N_STATES)
    ]
    ax.legend(
        handles   = handles,
        title     = "HMM State",
        fontsize  = 7,
        title_fontsize = 7,
        loc       = "upper left",
        framealpha= 0.7,
        ncol       = 2,
    )

plt.tight_layout()
plt.savefig("regime_detection.png", dpi=150, bbox_inches="tight")
plt.show()
print("\nFigure saved → regime_detection.png")


# %%
# ////// CELL 8 (Optional): Print Raw Regime Statistics per Ticker \\\\\\
# ─────────────────────────────────────────────────────────────────────────────
# Quick diagnostic: for each ticker print the count and mean for every
# feature broken out by state. Useful for interpreting what each regime means:
#   High Returns  + High Range  + High Vol_Change  →  Volatile Breakout
#   Low  Returns  + High Range  + Low  Vol_Change  →  Panic / Crash
#   Near-zero Returns + Low Range + Low Vol_Change →  Consolidation / Chop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("  DETAILED REGIME PROFILE (mean of features per state)")
print("=" * 65 + "\n")

for ticker in TICKERS:
    df_states = results[ticker]["df"]
    profile   = (
        df_states
        .groupby("State")[FEATURE_COLS]
        .agg(["mean", "std", "count"])
    )
    print(f"── {ticker} ──────────────────────────────────────────────")
    show(profile.round(6))
    print()
