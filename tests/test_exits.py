"""Unit tests for strategy/exits.py"""
import pytest
from strategy.exits import (
    check_trailing_stop,
    check_partial_exits,
    build_exit_thresholds,
    RECOMMENDED_LADDER,
    TRAILING_STOP_PCT,
)

# ── check_trailing_stop ───────────────────────────────────────────────────────

def test_trailing_stop_fires_at_threshold():
    # peak=100, 5% below = 95.0 exactly → fires
    assert check_trailing_stop(95.0, 100.0, 0.05) is True

def test_trailing_stop_fires_below_threshold():
    assert check_trailing_stop(90.0, 100.0, 0.05) is True

def test_trailing_stop_does_not_fire_above_threshold():
    assert check_trailing_stop(95.01, 100.0, 0.05) is False

def test_trailing_stop_does_not_fire_at_peak():
    assert check_trailing_stop(100.0, 100.0, 0.05) is False


# ── check_partial_exits ───────────────────────────────────────────────────────

_LADDER_3 = [
    {"gain_pct": 15, "sell_fraction": 0.10},   # non-remainder
    {"gain_pct": 30, "sell_fraction": 0.15},   # non-remainder
    {"gain_pct": 50, "sell_fraction": 0.50},   # remainder tier
]

def test_partial_exits_non_remainder_uses_sell_fraction():
    actions = check_partial_exits(
        gain_pct=20.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    assert len(actions) == 1
    assert actions[0]["gain_pct"] == 15
    assert abs(actions[0]["resolved_fraction"] - 0.10) < 1e-9

def test_partial_exits_skips_fired_tier():
    # +15% already fired; gain=20 → only +30% not yet reached, nothing fires
    actions = check_partial_exits(
        gain_pct=20.0, position_fraction=0.90,
        thresholds=_LADDER_3, tiers_fired={15}
    )
    assert len(actions) == 0

def test_partial_exits_no_action_below_threshold():
    actions = check_partial_exits(
        gain_pct=10.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    assert len(actions) == 0

def test_partial_exits_multiple_tiers_fire_same_bar():
    # gain=35 → +15% and +30% both fire (neither is the remainder at 50%)
    actions = check_partial_exits(
        gain_pct=35.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    fired = {a["gain_pct"] for a in actions}
    assert 15 in fired and 30 in fired

def test_partial_exits_remainder_accounts_for_sold_this_call():
    # All 3 tiers fire: sold_this_call = 0.10 + 0.15 = 0.25
    # remainder resolved = 0.50 × (1.0 - 0.25) = 0.375
    actions = check_partial_exits(
        gain_pct=60.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    remainder = next(a for a in actions if a["gain_pct"] == 50)
    assert abs(remainder["resolved_fraction"] - 0.375) < 1e-9

def test_partial_exits_remainder_uses_current_position_fraction():
    # position_fraction=0.75 (prior partials fired earlier), remainder fires alone
    actions = check_partial_exits(
        gain_pct=60.0, position_fraction=0.75,
        thresholds=_LADDER_3, tiers_fired={15, 30}
    )
    assert len(actions) == 1
    assert actions[0]["gain_pct"] == 50
    # sold_this_call=0 (no non-remainder fires), resolved = 0.50 × 0.75
    assert abs(actions[0]["resolved_fraction"] - 0.375) < 1e-9

def test_partial_exits_label_format():
    actions = check_partial_exits(
        gain_pct=20.0, position_fraction=1.0,
        thresholds=_LADDER_3, tiers_fired=set()
    )
    assert actions[0]["label"] == "Partial +15%"

def test_recommended_ladder_has_5_tiers():
    assert len(RECOMMENDED_LADDER) == 5

def test_recommended_ladder_gain_pcts():
    gains = [t["gain_pct"] for t in RECOMMENDED_LADDER]
    assert gains == [15, 30, 45, 60, 100]


# ── build_exit_thresholds ─────────────────────────────────────────────────────

def test_build_returns_recommended_ladder():
    result = build_exit_thresholds("recommended")
    assert result is RECOMMENDED_LADDER

def test_build_user_defined_valid():
    ladder = [
        {"gain_pct": 20, "sell_fraction": 0.10},
        {"gain_pct": 50, "sell_fraction": 0.20},
        {"gain_pct": 80, "sell_fraction": 0.50},
    ]
    assert build_exit_thresholds("user_defined", ladder) == ladder

def test_build_user_defined_not_ascending_raises():
    ladder = [
        {"gain_pct": 50, "sell_fraction": 0.10},
        {"gain_pct": 20, "sell_fraction": 0.20},
        {"gain_pct": 80, "sell_fraction": 0.50},
    ]
    with pytest.raises(ValueError, match="strictly ascending"):
        build_exit_thresholds("user_defined", ladder)

def test_build_user_defined_fractions_too_high_raises():
    # non-remainder sum = 0.60 + 0.40 = 1.0 → rejected (must be < 1.0)
    ladder = [
        {"gain_pct": 20, "sell_fraction": 0.60},
        {"gain_pct": 50, "sell_fraction": 0.40},
        {"gain_pct": 80, "sell_fraction": 0.50},
    ]
    with pytest.raises(ValueError):
        build_exit_thresholds("user_defined", ladder)

def test_build_invalid_mode_raises():
    with pytest.raises(ValueError):
        build_exit_thresholds("unknown_mode")

def test_build_user_defined_empty_raises():
    with pytest.raises(ValueError):
        build_exit_thresholds("user_defined", [])
