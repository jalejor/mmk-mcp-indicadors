"""Round 5 (`impulse-2.3.0`, docs/impulsos-v2.md §R5): ENTRY filters on the FROZEN 2.2.0 chain.

Every expected outcome is derived from the rule in the docstring, not from the code.
Fixtures reuse the round-2 S02 long setup (4h trigger, 1d guardian): leader verde zero
cross up at bar 10, AO zero cross up at 11, MACD cross up at 12 -> ENTER long at 12
unless the active entry filter blocks it. Golden windows W_f = 4 (alert ttl 4: alive
through bar 14, expired at 15). ML RSI regime columns are explicit (trigger green,
guardian gray) so the 2.2.0 gates pass, exactly as in tests/test_impulse_r4.py.
"""

import numpy as np
import pytest

from controllers.metrics.impulse_sequential import (
    R4_OVERRIDES,
    R5_OVERRIDES,
    SequentialMachine,
    r4_params,
    r5_params,
)
from controllers.metrics.impulse_service import ENTRY_FILTERS, RULE_VERSION_R5
from test_impulse_sequential import GOLDEN_WINDOWS, N, _frames, _long_setup

ALL_FILTERS = ("adx_turn", "adx_turn_origin", "ao_divergence", "ao_divergence_any_tf", "bbwp_fresh", "bbwp_fresh_blue")


def _p(entry_filter=None, **overrides):
    """PRO book + 2.2.0 chain + one entry filter, golden windows W_f = 4."""
    return r5_params("pro", entry_filter=entry_filter, confirm_window_bars=dict(GOLDEN_WINDOWS), **overrides)


def _f(trigger, d1="bullish", trig_regime="green", ctx_regime="gray"):
    frames = _frames(trigger, d1=d1, w1="bullish")
    frames["4h"]["ml_rsi_regime"] = trig_regime
    frames["1d"]["ml_rsi_regime"] = ctx_regime
    return frames


def _run(frames, params):
    return SequentialMachine(params, frames).run()


def _entries(decisions):
    return [i for i, d in enumerate(decisions) if d.action == "enter"]


def _with_adx_turn(t, base=20.0, after=26.0, at=13):
    """E1 onset at `at`: ADX flat `base` then `after` from `at` -> slope_recent (after-base)/3 >= 1,
    slope_prior 0 -> delta >= 1.5, ADX >= 10; +DI 25 > -DI 15 -> `adx_turn_up_long` at `at` only."""
    adx = np.full(N, float(base))
    adx[at:] = float(after)
    t["adx14"], t["plus_di"], t["minus_di"] = adx, 25.0, 15.0
    return t


def _with_bull_div(t, lower_low=True):
    """E2 bullish divergence on the trigger: AO pivot lows (strength 2) at bar 3 (-100) and bar 9 (-60),
    distance 6 in [5, 40]; price lows 59700 at 3 and 59500 at 9 (lower low) -> ao2 > ao1, pr2 < pr1,
    both AO < 0; pivot 9 confirmed at 11, ttl 10 -> ACTIVE at bar 12 (no later low breaks 59500).
    The AO zero cross up at 11 (-30 -> 50) is kept, so S02 still confirms AO at 11."""
    ao = np.full(N, -20.0)
    ao[2], ao[3], ao[4] = -50.0, -100.0, -50.0
    ao[8], ao[9], ao[10] = -30.0, -60.0, -30.0
    ao[11:] = 50.0
    t["ao"] = ao
    low = t["low"].to_numpy().copy()
    low[3] = 59700.0
    low[9] = 59500.0 if lower_low else 59900.0
    t["low"] = low
    return t


def _with_bbwp_breakout(t, breakout_at=10, before=20.0):
    """BBWP `before` until the candle before `breakout_at` - 1, 45 the candle before, 55 at `breakout_at`,
    60 after: breakout (cross > 50) at `breakout_at`; phase = ignition while breakout_age <= 2 and the
    min of the last 10 BBWP values <= 30; blue_recent iff that min <= 20."""
    bbwp = np.full(N, float(before))
    bbwp[breakout_at - 1] = 45.0
    bbwp[breakout_at] = 55.0
    bbwp[breakout_at + 1:] = 60.0
    t["bbwp"] = bbwp
    return t


# ---------------------------------------------------------------------------
# Params
# ---------------------------------------------------------------------------

def test_r5_params_freeze_the_2_2_0_chain_and_add_exactly_one_entry_filter():
    p = r5_params("snipper", entry_filter="adx_turn")
    r4 = r4_params("snipper")
    assert p.rule_version == RULE_VERSION_R5 == "impulse-2.3.0" and p.entry_filter == "adx_turn" and p.model == "sequential"
    for key, value in R4_OVERRIDES.items():
        if key != "rule_version":
            assert getattr(p, key) == value == getattr(r4, key), key
    assert (p.equity_usdt, p.leverage, p.margin_mode, p.maintenance_margin_rate) == (1700.0, 10.0, "isolated", 0.0056)
    assert p.confirm_window_bars == r4.confirm_window_bars == {"ao": 2, "adx": 5, "macd": 3, "rsi": 3}
    assert p.adx_origin_band == (12.0, 20.0)
    assert set(R5_OVERRIDES) == set(R4_OVERRIDES) and R5_OVERRIDES["rule_version"] == "impulse-2.3.0"
    base = r5_params("pro")
    assert base.entry_filter is None and base.rule_version == "impulse-2.3.0" and base.phase_lost_exit is False
    assert r4.rule_version == "impulse-2.2.0" and r4.entry_filter is None  # 2.2.0 untouched
    assert ENTRY_FILTERS == ALL_FILTERS
    with pytest.raises(ValueError):
        r5_params("pro", entry_filter="volume_spike")
    with pytest.raises(ValueError):
        r5_params("pro", adx_origin_band=(20.0, 12.0))


# ---------------------------------------------------------------------------
# Baseline = 2.2.0 entry, every flag reported
# ---------------------------------------------------------------------------

def test_baseline_enters_like_2_2_0_and_reports_every_flag_false_on_the_plain_s02():
    """S02 has no ADX confirmation, no AO pivots (zeros then 50), flat BBWP 60 (expansion, not
    ignition) and a constant guardian AO -> every filter is False, the entry is unchanged."""
    frames = _f(_long_setup())
    r5 = _run(frames, _p())
    r4 = _run(_f(_long_setup()), r4_params("pro", confirm_window_bars=dict(GOLDEN_WINDOWS)))
    assert [(d.action, d.side, d.notional) for d in r5] == [(d.action, d.side, d.notional) for d in r4]
    e = r5[12]
    assert e.action == "enter" and e.notional == pytest.approx(758.952, abs=1e-3)
    assert e.context["entry_filters"] == {name: False for name in ALL_FILTERS}
    assert {f"entry_filter:{name}=0" for name in ALL_FILTERS} <= set(e.reasons)
    assert not any(r.startswith("entry_filter_ok") or r.startswith("entry_filter_blocked") for r in e.reasons)


def test_force_enter_ignores_the_entry_filter():
    m = SequentialMachine(_p("ao_divergence"), _f(_long_setup()))
    d = m.force_enter(12, "long")
    assert d.action == "enter" and "forced_anchor" in d.reasons and m.state == "in_position"


# ---------------------------------------------------------------------------
# F1 adx_turn / adx_turn_origin
# ---------------------------------------------------------------------------

def test_adx_turn_filter_blocks_bar_12_then_enters_on_the_adx_confirmation_at_13():
    """Alert at 10 (W_adx = 4 -> ADX counts through 14). Bar 12: AO + MACD confirm but no ADX ->
    blocked, alert alive. Bar 13: E1 onset with +DI dominant -> adx confirms -> ENTER at 13.
    Origin = min ADX over [10, 13] = 20, inside [12, 20] -> adx_turn_origin also True."""
    t = _with_adx_turn(_long_setup())
    d = _run(_f(t), _p("adx_turn"))
    b = d[12]
    assert (b.action, b.state) == ("alert", "alert") and "entry_filter_blocked:adx_turn" in b.reasons
    assert b.context["entry_filters"]["adx_turn"] is False
    e = d[13]
    assert (e.action, e.side) == ("enter", "long") and _entries(d) == [13]
    assert e.confirmations["adx"] == {"side": 1, "bar": 13, "event": "adx_turn_up_long"}
    assert {"entry_filter_ok:adx_turn", "entry_filter:adx_turn=1", "entry_filter:adx_turn_origin=1"} <= set(e.reasons)
    assert e.context["entry_filters"]["adx_turn"] and e.context["entry_filters"]["adx_turn_origin"]
    # without any ADX turn the alert dies at 15 and nothing is ever entered
    d0 = _run(_f(_long_setup()), _p("adx_turn"))
    assert _entries(d0) == [] and d0[14].state == "alert" and d0[15].state == "flat" and "alert_expired" in d0[15].reasons


def test_adx_turn_origin_rejects_a_turn_born_above_the_band_and_the_band_is_a_parameter():
    """ADX 25 -> 31 at 13: same bend (slope 2, delta 2) but origin 25 is outside [12, 20]:
    `adx_turn` enters at 13, `adx_turn_origin` never enters; with band (12, 26) it enters."""
    t = _with_adx_turn(_long_setup(), base=25.0, after=31.0)
    d = _run(_f(t), _p("adx_turn"))
    assert _entries(d) == [13] and d[13].context["entry_filters"] == {**d[13].context["entry_filters"], "adx_turn": True, "adx_turn_origin": False}
    d = _run(_f(t), _p("adx_turn_origin"))
    assert _entries(d) == [] and "entry_filter_blocked:adx_turn_origin" in d[13].reasons and d[15].state == "flat"
    d = _run(_f(t), _p("adx_turn_origin", adx_origin_band=(12.0, 26.0)))
    assert _entries(d) == [13] and "entry_filter_ok:adx_turn_origin" in d[13].reasons
    # a turn born at the lower edge (12 -> 18) is A-grade
    d = _run(_f(_with_adx_turn(_long_setup(), base=12.0, after=18.0)), _p("adx_turn_origin"))
    assert _entries(d) == [13]


# ---------------------------------------------------------------------------
# F2 ao_divergence / ao_divergence_any_tf
# ---------------------------------------------------------------------------

def test_ao_divergence_filter_needs_an_active_bullish_divergence_on_the_trigger():
    t = _with_bull_div(_long_setup())
    d = _run(_f(t), _p("ao_divergence"))
    e = d[12]
    assert (e.action, e.side) == ("enter", "long") and _entries(d) == [12]
    assert {"entry_filter_ok:ao_divergence", "entry_filter:ao_divergence=1", "entry_filter:ao_divergence_any_tf=1"} <= set(e.reasons)
    assert e.invalidation_price == 59200.0  # S02 swing low still the widest level
    # same AO shape but price makes NO lower low (59900 at bar 9): not a divergence -> blocked until the alert dies
    t = _with_bull_div(_long_setup(), lower_low=False)
    d = _run(_f(t), _p("ao_divergence"))
    assert _entries(d) == [] and "entry_filter_blocked:ao_divergence" in d[12].reasons
    assert d[13].state == "alert" and d[14].state == "alert" and d[15].state == "flat"
    assert d[12].context["entry_filters"]["ao_divergence"] is False
    # the baseline still enters there and reports the flag as False
    assert _entries(_run(_f(t), _p())) == [12]


def test_ao_divergence_any_tf_accepts_the_guardian_divergence():
    """Trigger S02 (no divergence). Guardian 1d: AO -20 with pivot lows -100 at 18 and -60 at 24,
    lows 59300 at 18 and 59000 at 24 (lower low) -> bullish divergence confirmed at 26, active at 27.
    The 4h candle of bar 12 opens 2026-01-12 00:00 and closes 04:00; the last 1d candle closed by
    then opened 2026-01-11 = index 27 of a frame starting 2025-12-15. Guardian bias stays bullish
    (verde +3, DI +2, AO -2, MACD +1 = 4 >= 3). Guardian swing low over [18, 27] = 59000 is the
    widest invalidation."""
    frames = _f(_long_setup())
    g = frames["1d"]
    ao = np.full(len(g), -20.0)
    ao[17], ao[18], ao[19] = -50.0, -100.0, -50.0
    ao[23], ao[24], ao[25] = -30.0, -60.0, -30.0
    g["ao"] = ao
    low = g["low"].to_numpy().copy()
    low[18], low[24] = 59300.0, 59000.0
    g["low"] = low
    m = SequentialMachine(_p("ao_divergence_any_tf"), frames)
    assert int(m.ctx_idx["1d"][12]) == 27
    d = m.run()
    e = d[12]
    assert (e.action, e.side) == ("enter", "long") and _entries(d) == [12]
    assert e.context["entry_filters"]["ao_divergence"] is False and e.context["entry_filters"]["ao_divergence_any_tf"] is True
    assert "entry_filter_ok:ao_divergence_any_tf" in e.reasons and "context_aligned" in e.reasons
    assert (e.invalidation_price, e.invalidation_source) == (59000.0, "invalidation_ctx_swing")
    # the trigger-only variant does not accept it
    assert _entries(_run(frames, _p("ao_divergence"))) == []


# ---------------------------------------------------------------------------
# F3 bbwp_fresh / bbwp_fresh_blue
# ---------------------------------------------------------------------------

def test_bbwp_fresh_requires_the_ignition_phase_on_the_entry_candle():
    """Breakout at 10 -> at 12 breakout_age 2 <= 2 and min(last 10) = 20 <= 30 -> ignition -> enter.
    Breakout at 4 (its BBWP-origin alert expires at 9, before the verde leader at 10) -> age 8 at 12 ->
    expansion -> blocked while the Konkorde alert lives (12-14), never enters."""
    t = _with_bbwp_breakout(_long_setup(), breakout_at=10)
    d = _run(_f(t), _p("bbwp_fresh"))
    e = d[12]
    assert (e.action, e.phase) == ("enter", "ignition") and _entries(d) == [12]
    assert {"entry_filter_ok:bbwp_fresh", "entry_filter:bbwp_fresh=1", "entry_filter:bbwp_fresh_blue=1"} <= set(e.reasons)
    t = _with_bbwp_breakout(_long_setup(), breakout_at=4)
    d = _run(_f(t), _p("bbwp_fresh"))
    assert d[9].state == "flat" and d[10].alert_age == 0  # the BBWP alert of bar 4 is gone; bar 10 is a fresh Konkorde alert
    assert _entries(d) == [] and d[12].phase == "expansion" and "entry_filter_blocked:bbwp_fresh" in d[12].reasons
    assert d[14].state == "alert" and d[15].state == "flat"
    # plain S02 (BBWP 60 flat, phase expansion) is blocked too
    assert _entries(_run(_f(_long_setup()), _p("bbwp_fresh"))) == []


def test_bbwp_fresh_blue_also_requires_the_compression_to_come_from_the_blue_zone():
    """Compression at 25 (<= 30: ignition) but min(last 10) = 25 > 20: `bbwp_fresh` passes,
    `bbwp_fresh_blue` blocks; at 20 both pass."""
    t = _with_bbwp_breakout(_long_setup(), breakout_at=10, before=25.0)
    d = _run(_f(t), _p("bbwp_fresh"))
    assert _entries(d) == [12] and d[12].context["entry_filters"] == {**d[12].context["entry_filters"], "bbwp_fresh": True, "bbwp_fresh_blue": False}
    d = _run(_f(t), _p("bbwp_fresh_blue"))
    assert _entries(d) == [] and "entry_filter_blocked:bbwp_fresh_blue" in d[12].reasons
    d = _run(_f(_with_bbwp_breakout(_long_setup(), breakout_at=10, before=20.0)), _p("bbwp_fresh_blue"))
    assert _entries(d) == [12] and "entry_filter_ok:bbwp_fresh_blue" in d[12].reasons
