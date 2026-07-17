"""Integration tests for the v0.2.0 monitors assembly (monitors_v020.py).

Drives `build_monitors_v020` directly with synthetic enriched frames — no
network, no HTTP — to pin the H1 hierarchy behaviour that spans multiple
timeframes: Rule 1 override (CONFIRMED_BY_HIGHER_TF), Rule 2 p_false boosts
(and their cap / precedence), and the M2 emission wiring.
"""

import numpy as np
import pandas as pd

from controllers.metrics.monitors_v020 import build_monitors_v020

V2_FE_KEYS = {
    "timeframe", "direction", "state", "early_warning", "event_age",
    "consecutive_ao_candles", "adx_turn", "p_false", "cross_candle_ts",
    "color_flip_age", "p_false_boosts", "higher_tf", "ignition_from_below",
}
V2_FI_KEYS = {
    "timeframe", "direction", "state", "t0_age", "adx_turn", "confirmed_by",
    "follow_age", "whipsaw_age", "p_false_ignition", "p_false_boosts",
    "higher_tf", "shadow", "alertable", "t0_candle_ts",
}

_FREQ = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "D", "1w": "7D"}


def _frame(tf, n=40, *, ao=1.0, adx=20.0, plus=25.0, minus=15.0, bbwp=40.0,
           konkorde=5.0):
    """Benign enriched frame; scalar args may be arrays for the tail shape."""
    index = pd.date_range("2026-02-01", periods=n, freq=_FREQ[tf], tz="UTC")

    def col(value):
        if np.isscalar(value):
            return np.full(n, float(value))
        value = np.asarray(value, dtype=float)
        arr = np.full(n, value[0])
        arr[-len(value):] = value
        return arr

    return pd.DataFrame(
        {
            "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
            "volume": 1000.0,
            "sma200": 90.0, "sma50": 95.0, "ema50": 96.0, "ema200": 92.0,
            "adx14": col(adx), "plus_di": col(plus), "minus_di": col(minus),
            "ao": col(ao), "bbwp": col(bbwp), "atr14": 2.0,
            "konkorde_marron": col(konkorde),
        },
        index=index,
    )


def _build(frames):
    def ensure(tf):
        return frames[tf]

    return build_monitors_v020(dict(frames), ensure)


def _fe(monitors):
    return {(m["timeframe"], m["direction"]): m for m in monitors["false_entry_watch"]}


# Owner's canonical false-entry tail (M1-G1): cross down 5 candles ago, flat
# ADX (no turn), bearish DI (aligned -> no color flip) -> FALSE_ENTRY_PROBABLE.
_FALSE_DOWN = {
    "ao": np.array([0.5, -0.4, -0.8, -1.1, -1.3, -1.6, -1.8]),
    "adx": 20.0, "plus": 15.0, "minus": 28.0,
}
# VT-G1 rounded dome on BBWP.
_VT_DOME = np.array([60, 68, 75, 82, 88, 90, 88, 85, 81, 72], dtype=float)


def test_h1_rule2_vol_turn_boosts_opposing_lower_watch():
    frames = {
        "15m": _frame("15m"),
        "30m": _frame("30m", **_FALSE_DOWN),
        "1h": _frame("1h"),
        # 4h rounded rollover during a bearish 4h move -> implied bullish
        # retracement -> the 30m DOWN watch opposes it -> +0.10.
        "4h": _frame("4h", bbwp=_VT_DOME, plus=15.0, minus=28.0),
        "1d": _frame("1d"),
        "1w": _frame("1w"),
    }
    monitors = _build(frames)

    watch = _fe(monitors)[("30m", "down")]
    assert watch["state"] == "FALSE_ENTRY_PROBABLE"
    assert watch["p_false_boosts"] == [{"source_tf": "4h", "addend": 0.10}]
    assert watch["p_false"] == 0.80
    assert set(watch.keys()) == V2_FE_KEYS
    assert monitors["vol_turn_rounded"] == [
        {"timeframe": "4h", "variant": "v", "move_direction": "down"}
    ]


def test_h1_rule2_addends_stack_and_cap_at_090():
    frames = {
        "15m": _frame("15m"),
        "30m": _frame("30m", **_FALSE_DOWN),
        "1h": _frame("1h"),
        "4h": _frame("4h", bbwp=_VT_DOME, plus=15.0, minus=28.0),
        "1d": _frame("1d", bbwp=_VT_DOME, plus=15.0, minus=28.0),
        "1w": _frame("1w"),
    }
    watch = _fe(_build(frames))[("30m", "down")]
    assert watch["p_false_boosts"] == [
        {"source_tf": "4h", "addend": 0.10},
        {"source_tf": "1d", "addend": 0.15},
    ]
    assert watch["p_false"] == 0.90  # 0.70 + 0.25 capped


def test_h1_rule2_ignores_watches_aligned_with_the_retracement():
    # Same rollover but during a BULLISH 4h move: the implied retracement is
    # bearish, the 30m down watch aligns with it -> untouched 0.70.
    frames = {
        "15m": _frame("15m"),
        "30m": _frame("30m", **_FALSE_DOWN),
        "1h": _frame("1h"),
        "4h": _frame("4h", bbwp=_VT_DOME, plus=28.0, minus=15.0),
        "1d": _frame("1d"),
        "1w": _frame("1w"),
    }
    watch = _fe(_build(frames))[("30m", "down")]
    assert watch["p_false_boosts"] == []
    assert watch["p_false"] == 0.70


def test_h1_rule1_overrides_and_beats_rule2():
    # 1h CONFIRMED down (fresh E1-G1 bearish turn after a fresh down-cross)
    # protects the 30m down watch even though the 4h rollover would boost it:
    # Rule 1 always wins over Rule 2 (spec §I.3).
    adx_turn_tail = np.array([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    frames = {
        "15m": _frame("15m"),
        "30m": _frame("30m", **_FALSE_DOWN),
        "1h": _frame(
            "1h",
            ao=np.array([0.5, -0.4, -0.8, -1.1]),
            adx=adx_turn_tail, plus=15.0, minus=28.0,
        ),
        "4h": _frame("4h", bbwp=_VT_DOME, plus=15.0, minus=28.0),
        "1d": _frame("1d"),
        "1w": _frame("1w"),
    }
    monitors = _build(frames)
    fe = _fe(monitors)

    assert fe[("1h", "down")]["state"] == "CONFIRMED"
    watch = fe[("30m", "down")]
    assert watch["state"] == "CONFIRMED_BY_HIGHER_TF"
    assert watch["higher_tf"] == {"source_tf": "1h"}
    assert watch["p_false"] is None
    assert watch["p_false_boosts"] == []


def test_h1_rule1_walks_past_a_silent_1h_to_the_4h():
    # The 2026-07-13 shape: 30m adjudicated FALSE while the 4h confirmed the
    # same impulse and the 1h had no active watch -> the ladder walk still
    # finds the 4h; both fields reflect the true source.
    adx_turn_tail = np.array([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    frames = {
        "15m": _frame("15m"),
        "30m": _frame("30m", **_FALSE_DOWN),
        "1h": _frame("1h"),  # benign: no AO cross at all
        "4h": _frame(
            "4h",
            ao=np.array([0.5, -0.4, -0.8, -1.1]),
            adx=adx_turn_tail, plus=15.0, minus=28.0,
        ),
        "1d": _frame("1d"),
        "1w": _frame("1w"),
    }
    fe = _fe(_build(frames))

    assert fe[("4h", "down")]["state"] == "CONFIRMED"
    watch = fe[("30m", "down")]
    assert watch["state"] == "CONFIRMED_BY_HIGHER_TF"
    assert watch["higher_tf"] == {"source_tf": "4h"}


def test_m2_contrary_impulse_emitted_for_adjudicated_watch():
    # 30m FALSE_ENTRY_PROBABLE down + fresh bullish E1 turn on the same TF
    # (the contrary direction) inside k=5 -> contrary_impulse via trigger (a).
    ao_down_stale = np.array([0.5, -0.4, -0.8, -1.1, -1.3, -1.6, -1.8])
    adx_turn_tail = np.array([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5])
    frames = {
        "15m": _frame("15m"),
        "30m": _frame("30m", ao=ao_down_stale, adx=adx_turn_tail, plus=28.0, minus=15.0),
        "1h": _frame("1h"),
        "4h": _frame("4h"),
        "1d": _frame("1d"),
        "1w": _frame("1w"),
    }
    monitors = _build(frames)

    # The bullish turn confirms nothing for the DOWN cross (up_bearish needed)
    # -> still adjudicated false...
    watch = _fe(monitors)[("30m", "down")]
    assert watch["state"] == "FALSE_ENTRY_PROBABLE"
    # ...and IS the contrary evidence for the predicted bullish impulse.
    contrary = monitors["contrary_impulse"]
    assert len(contrary) == 1
    entry = contrary[0]
    assert entry["timeframe"] == "30m"
    assert entry["direction"] == "up"
    assert entry["profile"] == "snipper"
    assert entry["trigger"] == "contrary_adx_turn"
    assert entry["source"]["kind"] == "m1"
    assert entry["source"]["state"] == "FALSE_ENTRY_PROBABLE"
    assert entry["source"]["p_false"] == 0.70


def test_tf_status_reports_failed_timeframe_and_others_keep_working():
    frames = {
        "15m": _frame("15m"),
        "30m": _frame("30m", **_FALSE_DOWN),
        "4h": _frame("4h"),
        "1d": _frame("1d"),
        "1w": _frame("1w"),
    }

    def ensure(tf):
        if tf == "1h":
            raise ValueError("no closed 1h candles")
        return frames[tf]

    monitors = build_monitors_v020(dict(frames), ensure)

    assert monitors["tf_status"]["1h"].startswith("failed:")
    assert "no closed 1h candles" in monitors["tf_status"]["1h"]
    for tf in ("15m", "30m", "4h", "1d", "1w"):
        assert monitors["tf_status"][tf] == "ok"
    # The 30m watch still evaluated (its ladder simply skips the blind 1h).
    assert ("30m", "down") in _fe(monitors)
