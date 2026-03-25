"""
models/hmm.py
─────────────
Fit GaussianHMM on engineered features and label Bull/Bear/Neutral regimes.

Public API
──────────
  fit_hmm(df, n_states, random_state) →
      (df_out, bull_state_id, bear_state_id, state_summary, model, scaler)
  N_STATES       — default number of HMM hidden states (6)
  RANDOM_SEED    — default random seed (42)
  MIN_REGIME_BARS — minimum consecutive bars before a regime change is confirmed (3)
"""

import warnings
import numpy  as np
import pandas as pd
from hmmlearn.hmm          import GaussianHMM
from sklearn.preprocessing import StandardScaler

from pipeline.features import FEATURE_COLS

N_STATES     = 6
RANDOM_SEED  = 42
MIN_REGIME_BARS = 3   # regime must persist ≥ 3 consecutive bars to be confirmed


def _smooth_regimes(raw: np.ndarray, min_bars: int) -> np.ndarray:
    """
    Apply minimum-duration filter to a regime label array.

    Operates on the original predicted sequence (no cascade): short runs (< min_bars)
    are reverted to the previous confirmed regime, but only when the short run's label
    has never been confirmed before.  Bar 0 is always retained (its label is added to
    the confirmed set immediately).

    After the loop, i always lands on the first bar of a new (different) regime;
    the else branch (same label) is dead code for all bars after bar 0 and must
    not be given additional logic.
    """
    if len(raw) == 0:
        return raw.copy()

    smoothed   = raw.copy()
    n          = len(raw)
    prev_label = raw[0]
    confirmed  = {raw[0]}   # bar 0 is always confirmed
    i          = 1

    while i < n:
        if raw[i] != prev_label:
            # Measure run length of new regime in the *original* sequence
            j = i
            while j < n and raw[j] == raw[i]:
                j += 1
            run_length = j - i
            if run_length < min_bars and raw[i] not in confirmed:
                smoothed[i:j] = prev_label  # revert short run
            else:
                prev_label = raw[i]         # new regime confirmed
                confirmed.add(raw[i])
            i = j
        else:
            # Dead code after bar 0: i always lands on a new-regime bar after any run
            prev_label = raw[i]
            i += 1

    return smoothed


def fit_hmm(df: pd.DataFrame, n_states: int = N_STATES, random_state: int = RANDOM_SEED):
    """
    Fit a GaussianHMM on the three scaled features.

    Returns
    ───────
    df_out        — input df with 'HMM_State', 'Regime', 'HMM_Confidence' columns added
    bull_state_id — int, state with highest mean return
    bear_state_id — int, state with lowest mean return
    state_summary — pd.DataFrame with one row per state
    model         — fitted GaussianHMM
    scaler        — fitted StandardScaler

    Notes
    ─────
    'Regime' is smoothed: short runs (< MIN_REGIME_BARS) are reverted to the prior
    confirmed regime. 'HMM_State' retains raw model output. 'HMM_Confidence' is the
    row-wise max posterior probability from model.predict_proba — it is NOT adjusted
    for smoothing and always reflects the raw model output.

    Callers read HMM_Confidence from df["HMM_Confidence"]; it is NOT in the return tuple.
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

    means_orig   = scaler.inverse_transform(model.means_)
    return_means = means_orig[:, 0]

    bull_state_id = int(np.argmax(return_means))
    bear_state_id = int(np.argmin(return_means))

    if bull_state_id == bear_state_id:
        sorted_ids    = np.argsort(return_means)
        bear_state_id = int(sorted_ids[0])
        bull_state_id = int(sorted_ids[-1])

    def _label(s: int) -> str:
        if s == bull_state_id: return "Bull"
        if s == bear_state_id: return "Bear"
        return "Neutral"

    df_out = df.copy()
    df_out["HMM_State"] = states
    df_out["Regime"]    = df_out["HMM_State"].map(_label)

    # ── Minimum regime duration filter ────────────────────────────────────────
    raw_regime    = df_out["Regime"].values.copy()
    smooth_regime = _smooth_regimes(raw_regime, MIN_REGIME_BARS)
    df_out["Regime"] = smooth_regime

    # ── HMM_Confidence: row-wise max posterior probability ────────────────────
    proba = model.predict_proba(X_scaled)
    df_out["HMM_Confidence"] = proba.max(axis=1)

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
