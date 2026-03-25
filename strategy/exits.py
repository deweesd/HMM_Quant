"""
strategy/exits.py
─────────────────
Exit logic: trailing stop + partial exit ladder (pure functions, no side effects).

Public API
──────────
  TRAILING_STOP_PCT   — 0.05 (exit if price falls 5% below peak)
  RECOMMENDED_LADDER  — 5-tier profit-taking schedule
  check_trailing_stop(current_price, peak_price, stop_pct) → bool
  check_partial_exits(gain_pct, position_fraction, thresholds, tiers_fired) → list[dict]
  build_exit_thresholds(mode, user_ladder) → list[dict]
"""

TRAILING_STOP_PCT = 0.05   # exit if price drops 5% below peak since entry
MIN_REGIME_BARS   = 3      # defined in models/hmm.py; referenced here for clarity

RECOMMENDED_LADDER = [
    {"gain_pct": 15,  "sell_fraction": 0.10},
    {"gain_pct": 30,  "sell_fraction": 0.15},
    {"gain_pct": 45,  "sell_fraction": 0.20},
    {"gain_pct": 60,  "sell_fraction": 0.30},
    {"gain_pct": 100, "sell_fraction": 0.50},  # remainder tier — sell_fraction ignored at runtime
]


def check_trailing_stop(current_price: float, peak_price: float, stop_pct: float) -> bool:
    """Return True if price has fallen stop_pct or more below peak_price."""
    return current_price <= peak_price * (1.0 - stop_pct)


def check_partial_exits(
    gain_pct: float,
    position_fraction: float,
    thresholds: list,
    tiers_fired: set,
) -> list:
    """
    Return exit actions for tiers that fire at the current bar.

    Parameters
    ──────────
    gain_pct          — current unrealised gain from entry (%)
    position_fraction — fraction of original position still held (0.0–1.0)
    thresholds        — full exit ladder (list of dicts with gain_pct, sell_fraction)
    tiers_fired       — set of gain_pct values already triggered; skipped

    Returns
    ───────
    list[dict] with keys: gain_pct, resolved_fraction, label
    resolved_fraction is a fraction of the ORIGINAL position.
    For non-remainder tiers: resolved_fraction = sell_fraction from dict.
    For remainder tier (highest gain_pct): resolved_fraction =
      0.50 × (position_fraction - sum of non-remainder resolved_fractions
      that also fire in this same call).
    """
    sorted_tiers   = sorted(thresholds, key=lambda t: t["gain_pct"])
    max_gain_pct   = sorted_tiers[-1]["gain_pct"] if sorted_tiers else None
    actions        = []
    sold_this_call = 0.0

    for tier in sorted_tiers:
        tgain = tier["gain_pct"]
        if tgain in tiers_fired:
            continue
        if gain_pct < tgain:
            continue

        if tgain == max_gain_pct:
            resolved = 0.50 * (position_fraction - sold_this_call)
        else:
            resolved        = tier["sell_fraction"]
            sold_this_call += resolved

        actions.append({
            "gain_pct":          tgain,
            "resolved_fraction": resolved,
            "label":             f"Partial +{tgain}%",
        })

    return actions


def build_exit_thresholds(mode: str, user_ladder: list = None) -> list:
    """
    Return exit ladder for the given mode.

    Raises ValueError on bad mode or invalid user_ladder.
    Validation: gain_pct strictly ascending; non-remainder sell_fraction sum < 1.0.
    The last tier's (remainder) sell_fraction is ignored at runtime.
    """
    if mode == "recommended":
        return RECOMMENDED_LADDER

    if mode != "user_defined":
        raise ValueError(f"mode must be 'recommended' or 'user_defined', got {mode!r}")

    if not user_ladder:
        raise ValueError("user_ladder must be a non-empty list when mode='user_defined'")

    gain_pcts = [t["gain_pct"] for t in user_ladder]
    for i in range(1, len(gain_pcts)):
        if gain_pcts[i] <= gain_pcts[i - 1]:
            raise ValueError(
                f"user_ladder gain_pct values must be strictly ascending; "
                f"found {gain_pcts[i - 1]} followed by {gain_pcts[i]}"
            )

    non_remainder_sum = sum(t["sell_fraction"] for t in user_ladder[:-1])
    if non_remainder_sum >= 1.0:
        raise ValueError(
            f"user_ladder non-remainder sell_fraction values sum to "
            f"{non_remainder_sum:.4f} — must be strictly less than 1.0"
        )

    return user_ladder
