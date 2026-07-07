"""Golden cases for timeframe bands (spec §0.3, B0-G1/G2) and false-entry
vetoes (spec §B.3, FE-G1/G2/G3).

The FE goldens are pinned at their spec-stated defaults (max_event_age=3,
confirm_window=3). The ACTIVE rule documents ship the owner-relaxed windows
(5, spec §E Q10); the FE-G1 case is additionally asserted under the active
windows: the AO cross of age 5 is no longer stale, but the missing ADX turn
still vetoes — level never substitutes the turn.
"""

import pandas as pd
import pytest

from controllers.metrics.setup_definitions import (
    CONFIRM_WINDOW,
    DEFAULT_SETUPS,
    IMP_4H_LONG,
    IMP_4H_SHORT,
    MAX_EVENT_AGE,
    PB_1D_LONG,
    PB_1D_SHORT,
    Condition,
    SetupDefinition,
    VetoDefinition,
    mirror_setup,
    validate_setup,
)
from controllers.metrics.setup_service import (
    SetupService,
    SetupValidationError,
    band_for_timeframe,
    evaluate_vetoes,
)


def _s(values):
    return pd.Series(values, dtype=float)


def _df(**columns):
    length = max(len(v) for v in columns.values())
    padded = {
        key: [float("nan")] * (length - len(values)) + [float(v) for v in values]
        for key, values in columns.items()
    }
    return pd.DataFrame(padded)


# ---------------------------------------------------------------------------
# Band mapping (owner decision Q6)
# ---------------------------------------------------------------------------

def test_band_cut_low_below_4h_high_from_4h():
    for tf in ("1m", "5m", "15m", "30m", "1h", "2h"):
        assert band_for_timeframe(tf) == "low_tf"
    for tf in ("4h", "6h", "8h", "12h", "1d", "3d", "1w"):
        assert band_for_timeframe(tf) == "high_tf"
    with pytest.raises(ValueError):
        band_for_timeframe("42h")


# ---------------------------------------------------------------------------
# B0-G1 — loading a low_tf document with Konkorde -> validation error
# ---------------------------------------------------------------------------

def _low_tf_setup(**overrides) -> SetupDefinition:
    base = dict(
        rule_version="0.0.1-test",
        setup_id="TEST-1H-LONG",
        side="long",
        timeframe_band="low_tf",
        context_timeframe="1h",
        trigger_timeframe="1h",
        context_all_of=(Condition("bbwp_regime"),),
        trigger_all_of=(Condition("ao_positive"),),
    )
    base.update(overrides)
    return SetupDefinition(**base)


def test_b0_g1_low_tf_konkorde_condition_fails_validation():
    rogue = _low_tf_setup(trigger_all_of=(Condition("konkorde_zero_cross", "up"),))
    with pytest.raises(SetupValidationError):
        validate_setup(rogue)


def test_b0_g1_low_tf_konkorde_vol_turn_source_fails_validation():
    rogue = _low_tf_setup(
        invalidation_any_of=(Condition("vol_turn", "w_or_v_high", source="konkorde_marron"),)
    )
    with pytest.raises(SetupValidationError):
        validate_setup(rogue)


def test_b0_g1_timeframe_outside_band_fails_validation():
    rogue = _low_tf_setup(context_timeframe="4h")
    with pytest.raises(SetupValidationError):
        validate_setup(rogue)
    rogue_high = SetupDefinition(
        rule_version="0.0.1-test",
        setup_id="TEST-4H-LONG",
        side="long",
        timeframe_band="high_tf",
        context_timeframe="4h",
        trigger_timeframe="1h",  # low timeframe inside a high-band doc
        trigger_all_of=(Condition("ao_positive"),),
    )
    with pytest.raises(SetupValidationError):
        validate_setup(rogue_high)


def test_setup_service_validates_at_load():
    rogue = _low_tf_setup(trigger_all_of=(Condition("konkorde_state", "positive"),))
    with pytest.raises(SetupValidationError):
        SetupService(setups=[rogue])


# ---------------------------------------------------------------------------
# B0-G2 — runtime guard: Konkorde never votes in low_tf
# ---------------------------------------------------------------------------

def test_b0_g2_runtime_guard_konkorde_never_votes_in_low_tf():
    cond = Condition("konkorde_state", "positive")
    frame = _df(konkorde_marron=[30.0, 35.0], close=[100.0, 101.0])
    low_result, _ = SetupService._eval_condition(cond, frame, "low_tf")
    high_result, label = SetupService._eval_condition(cond, frame, "high_tf")
    assert low_result is None  # guarded: no vote, no support entry, score 0
    assert high_result is True  # same payload under high_tf: it votes
    assert label == "konkorde_state:positive"


def test_b0_g2_runtime_guard_in_full_evaluation():
    # A rogue low_tf document (constructed without validation) containing a
    # konkorde context condition: the guard strips it at evaluation time.
    rogue = _low_tf_setup(
        context_all_of=(Condition("bbwp_regime"), Condition("konkorde_state", "positive")),
        trigger_all_of=(Condition("ao_positive"), Condition("ao_rising")),
    )
    service = SetupService(setups=[])
    frame = _df(
        bbwp=[60.0, 65.0],
        konkorde_marron=[30.0, 35.0],
        ao=[0.5, 1.0],
        adx14=[20.0, 21.0],
        plus_di=[25.0, 25.0],
        minus_di=[15.0, 15.0],
        close=[100.0, 101.0],
    )
    evaluation = service.evaluate_setup(rogue, {"1h": frame})
    assert all("konkorde" not in item for item in evaluation.support)
    assert evaluation.context_ok is True  # the guarded condition contributes 0


# ---------------------------------------------------------------------------
# FE-G1 — the owner's exact case -> VETO (stale AO cross + flat ADX)
# ---------------------------------------------------------------------------

_FE_G1_FRAME = dict(
    ao=[-0.4, 0.3, 0.9, 1.4, 1.8, 2.1, 2.3],
    adx14=[24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4],
    plus_di=[30.0] * 9,
    minus_di=[15.0] * 9,
    konkorde_marron=[-1.0, 0.8, 1.5],
)


def _spec_default_vetoes():
    """The §B.3 golden defaults: max_event_age=3, confirm_window=3."""
    return (
        VetoDefinition("freshness", event="konkorde_zero_cross_up", max_event_age=3),
        VetoDefinition("freshness", event="ao_zero_cross_up", max_event_age=3),
        VetoDefinition("adx_confirmation", variant="up_bullish", confirm_window=3),
    )


def test_fe_g1_stale_ao_cross_and_no_adx_turn():
    frame = _df(**_FE_G1_FRAME)
    reasons, grade = evaluate_vetoes(_spec_default_vetoes(), frame, band="high_tf")
    assert reasons == ["stale_ao_cross", "no_adx_turn_confirmation"]
    assert grade is None


def test_fe_g1_under_owner_windows_adx_turn_still_mandatory():
    """Q10: with windows=5 the AO cross (age 5) is fresh again, but the
    missing ADX turn still suppresses the entry — level (25.4 >= 25 with
    dominant +DI) never substitutes the turn."""
    frame = _df(**_FE_G1_FRAME)
    reasons, _ = evaluate_vetoes(IMP_4H_LONG.vetoes, frame, band="high_tf")
    assert reasons == ["no_adx_turn_confirmation"]


# ---------------------------------------------------------------------------
# FE-G2 — fresh + confirmed -> NO veto
# ---------------------------------------------------------------------------

def test_fe_g2_fresh_and_confirmed_no_veto():
    frame = _df(
        ao=[-1.2, -0.6, -0.1, 0.5, 1.1],
        adx14=[18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5],
        plus_di=[28.0] * 9,
        minus_di=[15.0] * 9,
        konkorde_marron=[-0.5, 0.7, 1.3],
    )
    reasons, grade = evaluate_vetoes(_spec_default_vetoes(), frame, band="high_tf")
    assert reasons == []
    assert grade == "A"  # E1-G1 shape pivots from 18 (inside [12, 20])


# ---------------------------------------------------------------------------
# FE-G3 — fresh crosses but steady ADX -> VETO (isolates V2)
# ---------------------------------------------------------------------------

def test_fe_g3_steady_adx_vetoes_despite_fresh_crosses():
    frame = _df(
        ao=[-0.6, 0.4, 1.0],
        adx14=[16, 17.2, 18.4, 19.6, 20.8, 22.0, 23.2, 24.4, 25.6],
        plus_di=[28.0] * 9,
        minus_di=[15.0] * 9,
        konkorde_marron=[-0.3, 0.9],
    )
    reasons, _ = evaluate_vetoes(_spec_default_vetoes(), frame, band="high_tf")
    assert reasons == ["no_adx_turn_confirmation"]


def test_fe_v1_not_applied_to_unused_optional_evidence():
    """PB veto table: when the divergence path is the evidence, the konkorde
    cross freshness veto does not apply (the divergence keeps its TTL)."""
    frame = _df(
        ao=[-0.4, 0.3, 0.9, 1.4, 1.8, 2.1, 2.3],
        adx14=[18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5],
        plus_di=[28.0] * 9,
        minus_di=[15.0] * 9,
        konkorde_marron=[5.0] * 9,  # positive forever: cross is out of window
    )
    vetoes = (
        VetoDefinition("freshness", event="konkorde_zero_cross_up", max_event_age=3),
        VetoDefinition("adx_confirmation", variant="up_bullish", confirm_window=3),
    )
    reasons, _ = evaluate_vetoes(
        vetoes,
        frame,
        band="high_tf",
        satisfied_evidence=["ao_divergence:bullish"],
        optional_evidence=["konkorde_zero_cross:up", "ao_divergence:bullish"],
    )
    assert "stale_konkorde_cross" not in reasons

    # Same frame WITHOUT the evidence gating: the stale state does veto.
    reasons_ungated, _ = evaluate_vetoes(vetoes, frame, band="high_tf")
    assert "stale_konkorde_cross" in reasons_ungated


# ---------------------------------------------------------------------------
# Rule documents: owner decisions + mirrors
# ---------------------------------------------------------------------------

def test_owner_windows_are_5():
    assert MAX_EVENT_AGE == 5
    assert CONFIRM_WINDOW == 5


def test_default_setups_validate_and_cover_both_sides():
    for setup in DEFAULT_SETUPS:
        validate_setup(setup)
    assert {s.setup_id for s in DEFAULT_SETUPS} == {
        "PB-1D-LONG", "PB-1D-SHORT", "IMP-4H-LONG", "IMP-4H-SHORT",
    }
    assert {s.side for s in (PB_1D_SHORT, IMP_4H_SHORT)} == {"short"}


def test_mirror_is_strict_and_involutive():
    # Mirroring twice returns the original document (strict mirror).
    assert mirror_setup(PB_1D_SHORT) == PB_1D_LONG
    assert mirror_setup(IMP_4H_SHORT) == IMP_4H_LONG

    # Spot-check key mirrored conditions.
    short_elements = {c.element for c in PB_1D_SHORT.context_all_of}
    assert "close_below_sma200" in short_elements
    assert "rally_state" in short_elements
    trigger_elements = {(c.element, c.variant) for c in IMP_4H_SHORT.trigger_all_of}
    assert ("konkorde_zero_cross", "down") in trigger_elements
    assert ("ao_negative", "") in trigger_elements
    veto_events = {v.event for v in IMP_4H_SHORT.vetoes if v.veto == "freshness"}
    assert veto_events == {"konkorde_zero_cross_down", "ao_zero_cross_down"}
    adx_veto = [v for v in IMP_4H_SHORT.vetoes if v.veto == "adx_confirmation"][0]
    assert adx_veto.variant == "up_bearish"  # ADX rises on bearish impulses too
