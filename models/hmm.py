"""
models/hmm.py
─────────────
Fit GaussianHMM on engineered features and label Bull/Bear/Neutral regimes.

Public API
──────────
  fit_hmm(df, n_states, random_state) →
      (df_out, bull_state_id, bear_state_id, state_summary, model, scaler)
  N_STATES    — default number of HMM hidden states (6)
  RANDOM_SEED — default random seed (42)
"""

import warnings
import numpy  as np
import pandas as pd
from hmmlearn.hmm          import GaussianHMM
from sklearn.preprocessing import StandardScaler

from pipeline.features import FEATURE_COLS

N_STATES    = 6
RANDOM_SEED = 42


def fit_hmm(df: pd.DataFrame, n_states: int = N_STATES, random_state: int = RANDOM_SEED):
    """
    Fit a GaussianHMM on the three scaled features.

    Returns
    ───────
    df_out        — input df with 'HMM_State' and 'Regime' columns added
    bull_state_id — int, state with highest mean return
    bear_state_id — int, state with lowest mean return
    state_summary — pd.DataFrame with one row per state
    model         — fitted GaussianHMM
    scaler        — fitted StandardScaler
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
