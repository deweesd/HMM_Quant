"""Tests for the regime smoothing helper in models/hmm.py"""
import numpy as np
from models.hmm import _smooth_regimes, MIN_REGIME_BARS


def test_short_run_reverted():
    # B B N N B B B — NN is length 2 < MIN_REGIME_BARS=3 → reverted to B
    raw = np.array(["B", "B", "N", "N", "B", "B", "B"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["B", "B", "B", "B", "B", "B", "B"]


def test_long_run_kept():
    # B B N N N B B — NNN is length 3 >= 3 → kept
    raw = np.array(["B", "B", "N", "N", "N", "B", "B"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["B", "B", "N", "N", "N", "B", "B"]


def test_bar_0_always_retained():
    # Even if bar 0 starts a 1-bar run, it is kept (no prior context)
    raw = np.array(["N", "B", "B", "B", "B"])
    result = _smooth_regimes(raw, 3)
    # The N at bar 0 has no prior, so it is kept.
    # "B" run starting at bar 1 is length 4 >= 3 → confirmed.
    assert result[0] == "N"
    assert list(result[1:]) == ["B", "B", "B", "B"]


def test_final_short_run_reverted():
    # B B B N N — NN at the end is length 2 < 3 → reverted to B
    raw = np.array(["B", "B", "B", "N", "N"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["B", "B", "B", "B", "B"]


def test_cascading_prevented():
    # Operating on raw sequence prevents cascade:
    # B B N N B B B N N B B B
    # NN (pos 2-3): length 2 < 3 → reverted to B
    # BBB (pos 4-6): confirmed
    # NN (pos 7-8): length 2 < 3 → reverted to B (prev is B, from confirmed BBB)
    raw = np.array(["B","B","N","N","B","B","B","N","N","B","B","B"])
    result = _smooth_regimes(raw, 3)
    # All N runs reverted to B
    assert all(r == "B" for r in result)


def test_single_bar_sequence():
    raw = np.array(["Bull"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["Bull"]


def test_min_regime_bars_constant_is_3():
    assert MIN_REGIME_BARS == 3


def test_short_run_of_confirmed_label_kept():
    # Bull*3 confirmed, Bear*3 confirmed, Bull*2 — the trailing Bull*2 is below
    # min_bars=3, but Bull was previously confirmed, so it is KEPT (not reverted to Bear)
    raw = np.array(["Bull", "Bull", "Bull", "Bear", "Bear", "Bear", "Bull", "Bull"])
    result = _smooth_regimes(raw, 3)
    assert list(result) == ["Bull", "Bull", "Bull", "Bear", "Bear", "Bear", "Bull", "Bull"]
