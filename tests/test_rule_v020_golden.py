"""Golden cases for the v0.2.0 rule pack (docs/STRATEGY_SETUPS_SPEC.md §I).

Deterministic arrays straight from the spec (M11-G1/G2, VT-G1/G2, M2-G1,
M1m-G1/G2, C1micro-G1) plus precedence/edge cases. Numbers must not drift
without a rule_version bump. Everything here is v0.2.0-only: the last test
block pins that `false_entry_state` (v0.1.0) is NOT affected by the flip.
"""

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.rule_v020 import (
    CONFLUENCE_DEFAULTS,
    ConfluenceParams,
    FE_FALSE_ENTRY_CONFIRMED,
    FI_CONFIRMED,
    FI_FALSE_IGNITION_PROBABLE,
    FI_WHIPSAW,
    boosted_p_false,
    contrary_impulse,
    di_color_at,
    evaluate_confluence,
    false_entry_state_v2,
    false_ignition_state,
    higher_confirmed_source,
    p_false_boosts,
    v_turn_rounded_high,
    vol_turn_rounded_variant,
    w_turn_rounded_high,
)
from controllers.metrics.setup_service import (
    FE_CONFIRMED,
    FE_FALSE_ENTRY_PROBABLE,
    FE_WATCHING,
    FE_WHIPSAW,
    false_entry_state,
)


def _s(values):
    return pd.Series(values, dtype=float)


FLAT_ADX = _s([20] * 9)


# ---------------------------------------------------------------------------
# M1.1 — color flip (spec §I.1)
# ---------------------------------------------------------------------------

def test_m11_g1_color_flip_confirms_false_entry():
    # Spec M11-G1: cross up at index 1, DI aligned at t0, flips bearish at
    # post-cross age 2, no favorable turn -> FALSE_ENTRY_CONFIRMED (0.70,
    # measured prior — replay 120d 2026-07-16, n=243).
    ao = _s([-0.5, 0.4, 0.9, 0.7])
    plus_di = _s([26, 26, 26, 26, 26, 26, 27, 24, 19])
    minus_di = _s([16, 16, 16, 16, 16, 16, 17, 22, 25])

    fe = false_entry_state_v2(ao, FLAT_ADX, plus_di, minus_di, direction="up")

    assert fe.state == FE_FALSE_ENTRY_CONFIRMED
    assert fe.event_age == 2
    assert fe.color_flip_age == 2
    assert fe.p_false == 0.70
    assert fe.adx_turn is None


def test_m11_g1_bearish_mirror():
    ao = _s([0.5, -0.4, -0.9, -0.7])
    plus_di = _s([16, 16, 16, 16, 16, 16, 17, 22, 25])
    minus_di = _s([26, 26, 26, 26, 26, 26, 27, 24, 19])

    fe = false_entry_state_v2(ao, FLAT_ADX, plus_di, minus_di, direction="down")

    assert fe.state == FE_FALSE_ENTRY_CONFIRMED
    assert fe.color_flip_age == 2
    assert fe.p_false == 0.70


def test_m11_g2_flip_at_age_1_is_still_watching():
    # Spec M11-G2: flip at post-cross age 1 < color_min_age -> WATCHING.
    ao = _s([-0.5, 0.4, 0.7])
    plus_di = _s([26, 26, 26, 26, 26, 26, 26, 27, 19])
    minus_di = _s([16, 16, 16, 16, 16, 16, 16, 17, 24])

    fe = false_entry_state_v2(ao, FLAT_ADX, plus_di, minus_di, direction="up")

    assert fe.state == FE_WATCHING
    assert fe.color_flip_age is None
    assert fe.p_false is None


def test_flip_after_color_max_age_falls_to_timeout():
    # Flip only at post-cross age 5 (> color_max_age=4) -> ordinary age-5
    # timeout adjudication governs (0.40 measured timeout prior, not the
    # 0.70 flip prior — replay 120d 2026-07-16).
    ao = _s([-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8])
    plus_di = _s([26, 26, 26, 27, 27, 27, 27, 27, 19])
    minus_di = _s([16, 16, 16, 17, 17, 17, 17, 17, 25])

    fe = false_entry_state_v2(ao, FLAT_ADX, plus_di, minus_di, direction="up")

    assert fe.state == FE_FALSE_ENTRY_PROBABLE
    assert fe.p_false == 0.40
    assert fe.color_flip_age is None


def test_favorable_turn_overrides_color_flip():
    # A real impulse (E1 turn inside [t0, t0+5]) wins over the flip (§I.1).
    ao = _s([-0.5, 0.4, 0.9, 0.7])
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5, 24.6, 24.7])
    plus_di = _s([27, 27, 27, 27, 27, 27, 27, 27, 27, 24, 19])
    minus_di = _s([17, 17, 17, 17, 17, 17, 17, 17, 17, 22, 25])

    fe = false_entry_state_v2(ao, adx, plus_di, minus_di, direction="up")

    assert fe.state == FE_CONFIRMED
    # Youngest fire wins: the steep leg is still bending at age 1 (origin 18.5).
    assert fe.adx_turn == {"fired": True, "age": 1, "grade": "A"}
    assert fe.color_flip_age is None


def test_whipsaw_before_flip_wins():
    # AO re-crossed at post-cross age 1, before any flip could adjudicate.
    ao = _s([-0.5, 0.4, -0.2, -0.4])
    plus_di = _s([26, 26, 26, 26, 26, 26, 27, 24, 19])
    minus_di = _s([16, 16, 16, 16, 16, 16, 17, 22, 25])

    fe = false_entry_state_v2(ao, FLAT_ADX, plus_di, minus_di, direction="up")

    assert fe.state == FE_WHIPSAW
    assert fe.color_flip_age is None


def test_recross_after_flip_is_fulfilled_prediction_not_whipsaw():
    # Flip adjudicated at post-cross age 2; the later AO re-cross (post-age 4)
    # is the fulfilled contrary prediction -> stays FALSE_ENTRY_CONFIRMED.
    ao = _s([-0.5, 0.4, 0.6, 0.8, 0.5, -0.2])
    plus_di = _s([27, 27, 27, 27, 27, 27, 24, 22, 19])
    minus_di = _s([17, 17, 17, 17, 17, 17, 26, 24, 25])

    fe = false_entry_state_v2(ao, FLAT_ADX, plus_di, minus_di, direction="up")

    assert fe.state == FE_FALSE_ENTRY_CONFIRMED
    assert fe.color_flip_age == 2
    assert fe.p_false == 0.70


def test_di_already_contrary_at_cross_never_flips():
    # DI bearish at t0 (never aligned) -> no flip semantics; timeout governs.
    ao = _s([-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8])
    plus_di = _s([15] * 9)
    minus_di = _s([28] * 9)

    fe = false_entry_state_v2(ao, FLAT_ADX, plus_di, minus_di, direction="up")

    assert fe.state == FE_FALSE_ENTRY_PROBABLE
    assert fe.color_flip_age is None


def test_v1_false_entry_state_unaffected_by_flip_market():
    # CRITICAL no-regression: the v0.1.0 machine must keep answering WATCHING
    # on the M11-G1 market (the flip is a v0.2.0-only concept).
    ao = _s([-0.5, 0.4, 0.9, 0.7])
    plus_di = _s([26, 26, 26, 26, 26, 26, 27, 24, 19])
    minus_di = _s([16, 16, 16, 16, 16, 16, 17, 22, 25])

    fe = false_entry_state(ao, FLAT_ADX, plus_di, minus_di, direction="up")

    assert fe.state == FE_WATCHING
    assert fe.p_false is None


# ---------------------------------------------------------------------------
# E4.1 — vol_turn_rounded (spec §I.4)
# ---------------------------------------------------------------------------

def test_vt_g1_rounded_dome_fires():
    bbwp = _s([60, 68, 75, 82, 88, 90, 88, 85, 81, 72])
    assert v_turn_rounded_high(bbwp) is True
    assert vol_turn_rounded_variant(bbwp) == "v"


def test_vt_g2_last_candle_rising_no_fire():
    bbwp = _s([60, 68, 75, 82, 88, 90, 88, 85, 81, 84])
    assert v_turn_rounded_high(bbwp) is False
    assert vol_turn_rounded_variant(bbwp) is None


def test_vt_peak_below_zone_no_fire():
    bbwp = _s([40, 48, 55, 62, 68, 69, 66, 62, 58, 52])
    assert v_turn_rounded_high(bbwp) is False


def test_w_turn_rounded_double_test():
    # Two zone tests (79, 78) 4 bars apart, trough 68, last close falling;
    # cumulative drop 79-72=7 < 10 so the V variant stays silent -> "w".
    bbwp = _s([60, 74, 79, 71, 68, 73, 78, 76, 72])
    assert w_turn_rounded_high(bbwp) is True
    assert v_turn_rounded_high(bbwp) is False
    assert vol_turn_rounded_variant(bbwp) == "w"


def test_w_turn_rounded_second_peak_expanding_no_fire():
    # Second test exceeds the first by > tolerance -> fresh expansion, not W.
    bbwp = _s([60, 74, 79, 71, 68, 73, 88, 76, 72])
    assert w_turn_rounded_high(bbwp) is False


# ---------------------------------------------------------------------------
# H1 — hierarchy (spec §I.3 + addendum B.3.3)
# ---------------------------------------------------------------------------

def test_higher_confirmed_source_walks_the_ladder():
    # Nearest confirming TF above wins — a 4h CONFIRMED protects BOTH the 30m
    # and the 1h watch (the 2026-07-13 golden shape).
    confirmed = {"4h": ("down",)}
    assert higher_confirmed_source("30m", "down", confirmed) == "4h"
    assert higher_confirmed_source("1h", "down", confirmed) == "4h"
    assert higher_confirmed_source("4h", "down", confirmed) is None  # not above
    assert higher_confirmed_source("30m", "up", confirmed) is None  # direction


def test_higher_confirmed_source_15m_uses_30m_or_1h():
    assert higher_confirmed_source("15m", "up", {"30m": ("up",)}) == "30m"
    assert higher_confirmed_source("15m", "up", {"1h": ("up",)}) == "1h"


def test_p_false_boost_only_lower_tf_watches_opposing_the_retracement():
    moves = {"4h": "down"}  # 4h rollover during a bearish 4h move
    # A lower-TF watch in the SAME direction opposes the implied bullish
    # retracement -> boosted.
    # v0.2.1: addends are ZEROED pending Q19 — the wiring still emits the
    # boost entry (evidence), it just carries no weight.
    assert p_false_boosts("30m", "down", moves) == [
        {"source_tf": "4h", "addend": 0.0}
    ]
    # Opposite-direction watch aligns with the retracement -> no boost.
    assert p_false_boosts("30m", "up", moves) == []
    # A watch ON or ABOVE the rollover TF is never boosted by it.
    assert p_false_boosts("4h", "down", moves) == []
    assert p_false_boosts("1d", "down", moves) == []


def test_p_false_boost_1h_row_targets_micro_watches_only():
    moves = {"1h": "up"}
    assert p_false_boosts("15m", "up", moves) == [{"source_tf": "1h", "addend": 0.0}]
    assert p_false_boosts("30m", "up", moves) == [{"source_tf": "1h", "addend": 0.0}]
    # No 1h boost for... nothing below 1h other than micro exists; and a 30m
    # move on 4h/1d rows is unchanged:
    assert p_false_boosts("1h", "up", moves) == []


def test_boosted_p_false_caps_at_090():
    boosts = [{"source_tf": "4h", "addend": 0.10}, {"source_tf": "1d", "addend": 0.15}]
    assert boosted_p_false(0.80, boosts) == 0.90
    assert boosted_p_false(0.70, [{"source_tf": "4h", "addend": 0.10}]) == pytest.approx(0.80)
    assert boosted_p_false(0.70, []) == 0.70


# ---------------------------------------------------------------------------
# M2 — contrary_impulse (spec §I.2)
# ---------------------------------------------------------------------------

def test_m2_g1_contrary_adx_turn():
    # Adjudicated false UP-cross; within k=5 the same-TF ADX bends up with
    # -DI dominant (adx_turn_up_bearish) -> contrary impulse, trigger (a).
    ao = _s([-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8])
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    plus_di = _s([15] * 9)
    minus_di = _s([28] * 9)

    result = contrary_impulse(
        ao, adx, plus_di, minus_di, direction="up", adjudication_age=1
    )

    assert result is not None
    assert result.trigger == "contrary_adx_turn"
    assert result.confirmation_age == 0
    assert result.detail["grade"] == "A"


def test_m2_trigger_c_ao_recross_with_contrary_color():
    ao = _s([-0.5, 0.4, 0.8, 1.0, 1.2, 1.5, -0.2])
    plus_di = _s([15] * 9)
    minus_di = _s([28] * 9)

    result = contrary_impulse(
        ao, FLAT_ADX, plus_di, minus_di, direction="up", adjudication_age=0
    )

    assert result is not None
    assert result.trigger == "ao_recross_color"
    assert result.confirmation_age == 0


def test_m2_trigger_c_requires_contrary_color_on_recross_candle():
    ao = _s([-0.5, 0.4, 0.8, 1.0, 1.2, 1.5, -0.2])
    plus_di = _s([28] * 9)  # still bullish on the re-cross candle
    minus_di = _s([15] * 9)

    result = contrary_impulse(
        ao, FLAT_ADX, plus_di, minus_di, direction="up", adjudication_age=0
    )

    assert result is None


def test_m2_trigger_b_higher_tf_confirmed():
    ao = _s([-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8])  # no re-cross
    result = contrary_impulse(
        ao, FLAT_ADX, _s([28] * 9), _s([15] * 9),
        direction="up", adjudication_age=2,
        higher_confirmed_ages={"4h": 1},
    )
    assert result is not None
    assert result.trigger == "higher_tf_confirmed"
    assert result.detail == {"source_tf": "4h"}


def test_m2_confirmation_outside_k_window_is_ignored():
    # Turn fired at age 0 but the adjudication is 8 candles old: the k=5
    # window [3, 8] closed before the turn -> no contrary signal.
    ao = _s([-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8])
    adx = _s([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    result = contrary_impulse(
        ao, adx, _s([15] * 9), _s([28] * 9), direction="up", adjudication_age=8
    )
    assert result is None


# ---------------------------------------------------------------------------
# M1m — false ignition (addendum B.3.5)
# ---------------------------------------------------------------------------

# NOTE: the spec's M1m-G1 ADX series ([..., 19.2, 21.0]) does NOT fire E1 with
# the v0.1.0 defaults (delta_slope 1.467 < 1.5). Final value bumped 21.0 ->
# 21.5 (delta 1.633) so the anchor actually ignites — flagged to the owner in
# the PR as a spec erratum; every other number is verbatim.

M1M_ADX_T0_AT_5 = _s([15.8, 15.9, 16.0, 16.1, 16.2, 16.3, 17.5, 19.2, 21.5,
                      22.0, 22.3, 22.5, 22.6, 22.7])
M1M_ADX_T0_AT_8 = _s([15.8, 15.9, 16.0, 16.1, 16.2, 16.3, 17.5, 19.2, 21.5,
                      22.0, 22.3, 22.5, 22.6, 22.7, 22.8, 22.9, 23.0])


def test_m1m_g1_ignition_confirmed_by_ao_cross():
    ao = _s([-1.2, -1.0, -0.8, -0.5, -0.2, 0.3])
    plus_di = _s([28] * 14)
    minus_di = _s([15] * 14)
    bbwp = _s([40] * 14)

    fi = false_ignition_state(ao, M1M_ADX_T0_AT_5, plus_di, minus_di, bbwp, direction="up")

    assert fi.state == FI_CONFIRMED
    assert fi.t0_age == 5
    assert fi.adx_turn["grade"] == "A"          # origin 16.3 in [12, 20]
    assert fi.confirmed_by == "ao_cross"
    assert fi.follow_age == 5                    # AO crossed 5 candles after t0
    assert fi.p_false_ignition is None


def test_m1m_g2_ignition_without_body():
    ao = _s([-1.2, -1.1, -1.15, -1.1, -1.12, -1.1, -1.13, -1.1, -1.12])
    plus_di = _s([28] * 17)
    minus_di = _s([15] * 17)
    bbwp = _s([31, 30, 31, 30, 31, 30, 31, 30, 31])

    fi = false_ignition_state(ao, M1M_ADX_T0_AT_8, plus_di, minus_di, bbwp, direction="up")

    assert fi.state == FI_FALSE_IGNITION_PROBABLE
    assert fi.t0_age == 8
    assert fi.p_false_ignition == 0.42
    assert fi.confirmed_by is None


def test_m1m_confirmed_by_bbwp_expansion_with_di_color():
    # No AO cross, but BBWP rises 3 consecutive closes with the DI color
    # matching throughout -> body via volatility (addendum B.3.5).
    ao = _s([-1.2] * 14)
    plus_di = _s([28] * 14)
    minus_di = _s([15] * 14)
    bbwp = _s([40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 41, 43, 46, 46])

    fi = false_ignition_state(ao, M1M_ADX_T0_AT_5, plus_di, minus_di, bbwp, direction="up")

    assert fi.state == FI_CONFIRMED
    assert fi.confirmed_by == "bbwp_di"
    assert fi.follow_age == 3  # the 40->41->43 rising run completes at t0+3


def test_m1m_whipsaw_on_di_color_flip():
    adx = _s([15.8, 15.9, 16.0, 16.1, 16.2, 16.3, 17.5, 19.2, 21.5, 22.0, 22.3, 22.5])
    plus_di = _s([28] * 10 + [20, 18])
    minus_di = _s([15] * 10 + [24, 25])
    ao = _s([-1.2] * 12)
    bbwp = _s([40] * 12)

    fi = false_ignition_state(ao, adx, plus_di, minus_di, bbwp, direction="up")

    assert fi.t0_age == 3
    assert fi.state == FI_WHIPSAW
    assert fi.whipsaw_age == 1


def test_m1m_no_ignition_returns_none_state():
    fi = false_ignition_state(_s([-1.0] * 9), FLAT_ADX, _s([28] * 9), _s([15] * 9),
                              _s([40] * 9), direction="up")
    assert fi.state is None
    assert fi.t0_age is None


# ---------------------------------------------------------------------------
# C1 — confluence (spec §I.5 + addendum B.4.1)
# ---------------------------------------------------------------------------

def _c1_frame(n=30, *, ao, adx_shape, di, bbwp, konkorde=5.0):
    """Synthetic enriched frame for C1: adx_shape in {'rising','falling','turn'}."""
    if adx_shape == "rising":
        adx = np.linspace(15.0, 25.0, n)
    elif adx_shape == "falling":
        adx = np.linspace(25.0, 15.0, n)
    else:  # a fresh E1-G1 turn on the last candles
        adx = np.full(n, 18.0)
        adx[-3:] = [18.5, 21.5, 24.5]
    plus, minus = (28.0, 15.0) if di == "bullish" else (15.0, 28.0)
    return pd.DataFrame(
        {
            "ao": np.full(n, float(ao)),
            "adx14": adx,
            "plus_di": np.full(n, plus),
            "minus_di": np.full(n, minus),
            "bbwp": np.full(n, float(bbwp)),
            "konkorde_marron": np.full(n, float(konkorde)),
        }
    )


def test_c1_low_window_fires_bear_when_fully_aligned():
    frames = {
        "30m": _c1_frame(ao=-1.0, adx_shape="rising", di="bearish", bbwp=62),
        "1h": _c1_frame(ao=-0.8, adx_shape="rising", di="bearish", bbwp=58),
        "4h": _c1_frame(ao=-1.2, adx_shape="rising", di="bearish", bbwp=64, konkorde=-4.0),
        "1d": _c1_frame(ao=1.0, adx_shape="falling", di="bullish", bbwp=40),
        "1w": _c1_frame(ao=1.0, adx_shape="falling", di="bullish", bbwp=40),
    }
    entries = evaluate_confluence(frames)

    ids = {(e["window_id"], e["direction"]) for e in entries}
    assert ("30m-1h-4h", "bear") in ids
    entry = next(e for e in entries if e["window_id"] == "30m-1h-4h")
    assert entry["profiles"] == ["snipper", "pro"]
    assert entry["annotation"] == "1d probablemente en retroceso"
    assert entry["exit_priority"] == 5
    assert all(entry["alignment"][tf]["aligned"] for tf in ("30m", "1h", "4h"))
    # The Ancient window must NOT fire (1d/1w are misaligned).
    assert not any(e["window_id"] == "4h-1d-1w" for e in entries)


def test_c1_high_window_requires_konkorde_agreement():
    aligned = {
        "4h": _c1_frame(ao=1.0, adx_shape="rising", di="bullish", bbwp=60, konkorde=4.0),
        "1d": _c1_frame(ao=0.8, adx_shape="rising", di="bullish", bbwp=55, konkorde=3.0),
        "1w": _c1_frame(ao=0.6, adx_shape="rising", di="bullish", bbwp=52, konkorde=-1.0),
    }
    # 1w Konkorde disagrees -> 4/4 fails -> no Ancient window.
    assert not any(
        e["window_id"] == "4h-1d-1w" for e in evaluate_confluence(aligned)
    )
    aligned["1w"] = _c1_frame(ao=0.6, adx_shape="rising", di="bullish", bbwp=52, konkorde=2.0)
    entries = evaluate_confluence(aligned)
    entry = next(e for e in entries if e["window_id"] == "4h-1d-1w")
    assert entry["direction"] == "bull"
    assert entry["profiles"] == ["ancient"]
    assert entry["annotation"] == "1w probablemente en retroceso"


def test_c1_micro_g1_ao_is_bonus_not_gate():
    # Addendum C1micro-G1: 15m aligned on ADX+BBWP with AO bonus missing
    # (score 85), 30m full (score 100), 1h 3/3 -> Snipper entry fires.
    frames = {
        "15m": _c1_frame(ao=-0.2, adx_shape="turn", di="bullish", bbwp=58),
        "30m": _c1_frame(ao=0.1, adx_shape="rising", di="bullish", bbwp=61),
        "1h": _c1_frame(ao=0.5, adx_shape="rising", di="bullish", bbwp=55),
        "4h": _c1_frame(ao=0.5, adx_shape="falling", di="bearish", bbwp=41, konkorde=-2.0),
    }
    entries = evaluate_confluence(frames)

    micro = next(e for e in entries if e["window_id"] == "15m-30m-1h")
    assert micro["direction"] == "bull"
    assert micro["profiles"] == ["snipper"]
    assert micro["annotation"] == "4h probablemente en retroceso"
    assert micro["alignment"]["15m"]["score"] == 85
    assert micro["alignment"]["15m"]["components"]["ao"] is False
    assert micro["alignment"]["30m"]["score"] == 100
    assert micro["companion_ok"] is True  # 4h AO carries the same sign
    # 4h is misaligned -> the {30m,1h,4h} window must not fire.
    assert not any(e["window_id"] == "30m-1h-4h" for e in entries)


def test_c1_micro_requires_both_mandatory_components():
    # Same market but the 15m BBWP is dead (<=50, falling) -> no micro window.
    frames = {
        "15m": _c1_frame(ao=-0.2, adx_shape="turn", di="bullish", bbwp=40),
        "30m": _c1_frame(ao=0.1, adx_shape="rising", di="bullish", bbwp=61),
        "1h": _c1_frame(ao=0.5, adx_shape="rising", di="bullish", bbwp=55),
    }
    assert not any(
        e["window_id"] == "15m-30m-1h" for e in evaluate_confluence(frames)
    )


def test_c1_mid_window_is_q18_gated_default_off():
    frames = {
        "1h": _c1_frame(ao=0.5, adx_shape="rising", di="bullish", bbwp=55),
        "4h": _c1_frame(ao=1.0, adx_shape="rising", di="bullish", bbwp=60, konkorde=4.0),
        "1d": _c1_frame(ao=0.8, adx_shape="rising", di="bullish", bbwp=55, konkorde=3.0),
    }
    default = evaluate_confluence(frames, params=CONFLUENCE_DEFAULTS)
    assert not any(e["window_id"] == "1h-4h-1d" for e in default)

    enabled = evaluate_confluence(
        frames, params=ConfluenceParams(enable_mid_window=True)
    )
    assert any(e["window_id"] == "1h-4h-1d" for e in enabled)


# ---------------------------------------------------------------------------
# di_color primitive
# ---------------------------------------------------------------------------

def test_di_color_at_handles_age_tie_and_missing():
    plus = _s([28, 20, 18])
    minus = _s([15, 20, 25])
    assert di_color_at(plus, minus, age=0) == "bearish"
    assert di_color_at(plus, minus, age=1) is None  # tie is never a flip
    assert di_color_at(plus, minus, age=2) == "bullish"
    assert di_color_at(None, minus) is None
    assert di_color_at(plus, minus, age=9) is None
