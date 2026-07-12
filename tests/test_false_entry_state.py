"""M1 false_entry_watch golden cases from docs/STRATEGY_SETUPS_SPEC.md §B.3.1.

Deterministic arrays straight from the spec (M1-G1..G4) plus the strict
bearish mirrors. Numbers must not drift without a rule_version bump.
"""

import pandas as pd

from controllers.metrics.setup_service import (
    FE_CONFIRMED,
    FE_FALSE_ENTRY_PROBABLE,
    FE_WATCHING,
    FE_WHIPSAW,
    adx_turn_fired_between,
    false_entry_state,
)


def _s(values):
    return pd.Series(values, dtype=float)


# ---------------------------------------------------------------------------
# M1-G1 — owner's canonical case -> FALSE_ENTRY_PROBABLE
# ---------------------------------------------------------------------------

def test_m1_g1_false_entry_probable():
    ao = _s([-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8])
    adx = _s([24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4])
    plus_di = _s([28] * 9)
    minus_di = _s([15] * 9)

    fe = false_entry_state(ao, adx, plus_di, minus_di, direction="up")

    assert fe.state == FE_FALSE_ENTRY_PROBABLE
    assert fe.event_age == 5           # cross at index 1, evaluated at index 6
    assert fe.adx_turn is None         # constant slope -> no turn ever fires
    assert fe.p_false == 0.70
    assert fe.early_warning is False   # early_warning is superseded by the terminal state
    assert fe.consecutive_ao_candles >= 2


def test_m1_g1_bearish_mirror():
    ao = _s([0.5, -0.4, -0.8, -1.1, -1.3, -1.6, -1.8])
    adx = _s([24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4])
    plus_di = _s([15] * 9)
    minus_di = _s([28] * 9)

    fe = false_entry_state(ao, adx, plus_di, minus_di, direction="down")

    assert fe.state == FE_FALSE_ENTRY_PROBABLE
    assert fe.event_age == 5
    assert fe.adx_turn is None
    assert fe.p_false == 0.70


# ---------------------------------------------------------------------------
# M1-G2 — confirmed impulse -> CONFIRMED
# ---------------------------------------------------------------------------

def test_m1_g2_confirmed():
    ao = _s([-0.5, 0.4, 0.8, 1.1, 1.3])
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    plus_di = _s([28] * 9)
    minus_di = _s([15] * 9)

    fe = false_entry_state(ao, adx, plus_di, minus_di, direction="up")

    assert fe.state == FE_CONFIRMED
    assert fe.event_age == 3           # cross at index 1, turn within 5 candles
    assert fe.adx_turn == {"fired": True, "age": 0, "grade": "A"}
    assert fe.p_false is None


def test_m1_g2_bearish_mirror():
    ao = _s([0.5, -0.4, -0.8, -1.1, -1.3])
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    plus_di = _s([15] * 9)
    minus_di = _s([28] * 9)

    fe = false_entry_state(ao, adx, plus_di, minus_di, direction="down")

    assert fe.state == FE_CONFIRMED
    assert fe.adx_turn == {"fired": True, "age": 0, "grade": "A"}


# ---------------------------------------------------------------------------
# M1-G3 — fast whipsaw -> WHIPSAW
# ---------------------------------------------------------------------------

def test_m1_g3_whipsaw():
    ao = _s([-0.5, 0.3, 0.1, -0.2, -0.6])

    fe = false_entry_state(ao, direction="up")

    assert fe.state == FE_WHIPSAW      # re-cross down at index 3 (age 2 < 5)
    assert fe.whipsaw_age == 1
    assert fe.p_false is None


def test_m1_g3_bearish_mirror():
    ao = _s([0.5, -0.3, -0.1, 0.2, 0.6])

    fe = false_entry_state(ao, direction="down")

    assert fe.state == FE_WHIPSAW
    assert fe.whipsaw_age == 1


# ---------------------------------------------------------------------------
# M1-G4 — early warning isolate (watch still open)
# ---------------------------------------------------------------------------

def test_m1_g4_early_warning():
    ao = _s([-0.5, 0.4, 0.9, 1.5])
    adx = _s([20] * 9)

    fe = false_entry_state(ao, adx, _s([28] * 9), _s([15] * 9), direction="up")

    assert fe.state == FE_WATCHING
    assert fe.early_warning is True
    assert fe.event_age == 2
    assert fe.consecutive_ao_candles == 2
    assert fe.adx_turn is None


def test_m1_g4_bearish_mirror():
    ao = _s([0.5, -0.4, -0.9, -1.5])
    adx = _s([20] * 9)

    fe = false_entry_state(ao, adx, _s([15] * 9), _s([28] * 9), direction="down")

    assert fe.state == FE_WATCHING
    assert fe.early_warning is True
    assert fe.consecutive_ao_candles == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_cross_returns_none_state():
    ao = _s([1.0, 1.1, 1.2, 1.3])   # already positive, never crosses up from <=0
    fe = false_entry_state(ao, direction="up")
    assert fe.state is None
    assert fe.event_age is None


def test_watching_without_early_warning():
    # Cross up, but the first post-cross candle falls -> run breaks at 1.
    ao = _s([-0.5, 0.4, 0.3, 0.6])
    adx = _s([20] * 9)
    fe = false_entry_state(ao, adx, _s([28] * 9), _s([15] * 9), direction="up")
    assert fe.state == FE_WATCHING
    assert fe.early_warning is False
    assert fe.consecutive_ao_candles == 0


def test_bearish_confirmation_is_up_bearish_never_down():
    # A bullish ADX ignition (plus_di dominant) must NOT confirm a DOWN cross.
    ao = _s([0.5, -0.4, -0.8, -1.1, -1.3])
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    plus_di = _s([28] * 9)   # bullish dominance
    minus_di = _s([15] * 9)
    fe = false_entry_state(ao, adx, plus_di, minus_di, direction="down")
    # No up_bearish turn (DI is bullish) -> not confirmed.
    assert fe.state != FE_CONFIRMED


def test_adx_turn_fired_between_window():
    # Turn fires on the last candle (age 0); windows that exclude age 0 miss it.
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    plus_di = _s([28] * 9)
    minus_di = _s([15] * 9)
    hit = adx_turn_fired_between(adx, plus_di, minus_di, variant="up_bullish", age_lo=0, age_hi=3)
    assert hit is not None and hit.age == 0 and hit.grade == "A"
    miss = adx_turn_fired_between(adx, plus_di, minus_di, variant="up_bullish", age_lo=1, age_hi=3)
    assert miss is None
