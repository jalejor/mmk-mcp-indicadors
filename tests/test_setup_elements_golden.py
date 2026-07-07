"""Golden cases from docs/STRATEGY_SETUPS_SPEC.md §A (E1-E5).

Every case is a deterministic array of CLOSED-candle values -> expected
boolean, straight from the spec. Numbers must not drift without a
rule_version bump.
"""

import pandas as pd
import pytest

from controllers.metrics.setup_service import (
    AdxTurnParams,
    ao_divergence,
    adx_turn,
    adx_turn_fired_within,
    bbwp_regime_on,
    konkorde_positive,
    v_turn_high,
    vol_turn_high,
    w_turn_high,
    zero_cross_age,
)


def _s(values):
    return pd.Series(values, dtype=float)


# ---------------------------------------------------------------------------
# E1 — adx_turn
# ---------------------------------------------------------------------------

def test_e1_g1_sharp_turn_up_bullish():
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    plus_di = _s([28] * 9)
    minus_di = _s([15] * 9)
    result = adx_turn(adx, plus_di, minus_di)
    assert result.turn_up is True
    assert result.turn_up_bullish is True
    assert result.turn_up_bearish is False


def test_e1_g2_steady_rise_is_not_a_turn():
    adx = _s([16, 17.2, 18.4, 19.6, 20.8, 22, 23.2, 24.4, 25.6])
    result = adx_turn(adx, _s([28] * 9), _s([15] * 9))
    assert result.turn_up is False


def test_e1_g3_bend_too_weak():
    adx = _s([15, 15, 15, 15, 15, 15, 15.3, 15.6, 16.2])
    result = adx_turn(adx, _s([20] * 9), _s([18] * 9))
    assert result.turn_up is False


def test_e1_g4_turn_down():
    adx = _s([32, 31.5, 31, 30.5, 30, 29.5, 28, 25, 22])
    result = adx_turn(adx, _s([15] * 9), _s([28] * 9))
    assert result.turn_down is True


def test_e1_origin_grading_a_vs_b():
    """Owner refinement: pivot from ~16 -> A-grade; same shape from 31 -> B."""
    # Same shape as E1-G1: flat leg then a sharp bend. Origin = 16.2.
    adx_a = _s([16.2, 16.2, 16.2, 16.2, 16.2, 16.2, 16.7, 19.7, 22.7])
    result_a = adx_turn(adx_a, _s([28] * 9), _s([15] * 9))
    assert result_a.turn_up is True
    assert result_a.origin_level == pytest.approx(16.2)
    assert result_a.grade == "A"

    # Identical shape shifted so the pivot sits at 31 -> B-grade.
    adx_b = _s([31, 31, 31, 31, 31, 31, 31.5, 34.5, 37.5])
    result_b = adx_turn(adx_b, _s([28] * 9), _s([15] * 9))
    assert result_b.turn_up is True
    assert result_b.origin_level == pytest.approx(31.0)
    assert result_b.grade == "B"


def test_e1_fired_within_window():
    """A turn that fired one candle ago is found with window >= 2."""
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5, 21.0])
    plus_di = _s([28] * 10)
    minus_di = _s([15] * 10)
    assert adx_turn(adx, plus_di, minus_di).turn_up is False  # not on the last candle
    fire = adx_turn_fired_within(adx, plus_di, minus_di, variant="up_bullish", window=2)
    assert fire is not None and fire.age == 1
    assert adx_turn_fired_within(adx, plus_di, minus_di, variant="up_bullish", window=1) is None


def test_e1_custom_params_respected():
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    strict = AdxTurnParams(min_delta_slope=3.0)
    assert adx_turn(adx, _s([28] * 9), _s([15] * 9), strict).turn_up is False


# ---------------------------------------------------------------------------
# E2 — AO divergence + zero-cross events
# ---------------------------------------------------------------------------

_E2_LOW = [10.0, 9.5, 9.0, 9.5, 10.0, 10.5, 10.2, 9.4, 8.8, 9.2, 9.8, 10.1]


def test_e2_g1_bullish_divergence_true():
    ao = _s([-1.0, -1.5, -2.0, -1.6, -1.1, -0.8, -1.0, -1.3, -1.5, -1.2, -0.9, -0.5])
    low = _s(_E2_LOW)
    # Fires at bar 10 (p2=8 + strength 2): active at bars 10 and 11.
    at_bar_10 = ao_divergence(ao.iloc[:11], low=low.iloc[:11], side="bullish")
    assert at_bar_10.active is True and at_bar_10.fired_age == 0
    at_bar_11 = ao_divergence(ao, low=low, side="bullish")
    assert at_bar_11.active is True and at_bar_11.fired_age == 1
    assert (at_bar_11.pivot_1, at_bar_11.pivot_2) == (2, 8)


def test_e2_g2_ao_confirms_the_low_no_divergence():
    ao = _s([-1.0, -1.5, -2.0, -1.6, -1.1, -0.8, -1.2, -1.8, -2.6, -2.0, -1.4, -1.0])
    low = _s(_E2_LOW)
    assert ao_divergence(ao, low=low, side="bullish").active is False


def test_e2_g3_bearish_divergence_true():
    high = _s([100.0, 100.5, 101.0, 100.5, 100.0, 99.5, 99.8, 100.6, 101.2, 100.8, 100.2, 99.9])
    ao = _s([1.0, 1.5, 2.0, 1.6, 1.1, 0.8, 1.0, 1.3, 1.5, 1.2, 0.9, 0.5])
    result = ao_divergence(ao, high=high, side="bearish")
    assert result.active is True
    assert (result.pivot_1, result.pivot_2) == (2, 8)


def test_e2_ao_zero_cross_age_golden():
    """ao = [-0.4, 0.3, ...] -> cross fired at index 1, age 5 at index 6."""
    ao = _s([-0.4, 0.3, 0.9, 1.4, 1.8, 2.1, 2.3])
    assert zero_cross_age(ao, direction="up") == 5
    assert zero_cross_age(ao, direction="down") is None


# ---------------------------------------------------------------------------
# E3 — konkorde_zero_cross (event) vs state
# ---------------------------------------------------------------------------

def test_e3_g1_plain_cross_up():
    marron = _s([-5.0, -2.0, -0.5, 1.2])
    assert zero_cross_age(marron, direction="up", confirm_bars=1) == 0


def test_e3_g2_event_is_not_state():
    marron = _s([-5.0, -2.0, 0.5, 1.2])
    # The cross happened one candle earlier: event age 1, but the state is on.
    assert zero_cross_age(marron, direction="up", confirm_bars=1) == 1
    assert konkorde_positive(marron) is True


def test_e3_g3_cross_down():
    marron = _s([3.0, 2.0, 1.0, -0.8])
    assert zero_cross_age(marron, direction="down", confirm_bars=1) == 0


def test_e3_g4_confirm_bars_2_fires_one_candle_later():
    marron = _s([-2.0, 0.5, 1.2])
    assert zero_cross_age(marron, direction="up", confirm_bars=2) == 0
    # With confirm_bars=1 the same series fired one candle earlier (age 1).
    assert zero_cross_age(marron, direction="up", confirm_bars=1) == 1


# ---------------------------------------------------------------------------
# E4 — vol_turn (V / W in the high zone)
# ---------------------------------------------------------------------------

def test_e4_g1_v_turn_true():
    assert v_turn_high(_s([55, 62, 74, 86, 71])) is True


def test_e4_g2_still_rising_no_v_turn():
    assert v_turn_high(_s([55, 62, 74, 86, 88])) is False


def test_e4_g3_w_turn_true():
    assert w_turn_high(_s([60, 72, 84, 76, 70, 75, 83, 72])) is True


def test_e4_g4_second_peak_expands_no_w_turn():
    assert w_turn_high(_s([60, 72, 84, 76, 70, 80, 95, 90])) is False


def test_e4_vol_turn_high_is_v_or_w():
    assert vol_turn_high(_s([55, 62, 74, 86, 71])) is True
    assert vol_turn_high(_s([60, 72, 84, 76, 70, 75, 83, 72])) is True
    assert vol_turn_high(_s([40, 45, 50, 48, 47])) is False  # below the zone


# ---------------------------------------------------------------------------
# E5 — bbwp_regime
# ---------------------------------------------------------------------------

def test_e5_regime_strictly_above_50():
    assert bbwp_regime_on(_s([40.0, 50.0])) is False
    assert bbwp_regime_on(_s([40.0, 50.1])) is True
    assert bbwp_regime_on(_s([40.0, 49.9])) is False
