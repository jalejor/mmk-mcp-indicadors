"""R-TURN-IGNITION monitor (shadow candidate 0.3.x, spec pre-registered
2026-07-25) — the E1 grade-A ADX turn's standalone persist-only surface.

Pins the pre-registered rule EXACTLY (any drift invalidates the forward gate):
TFs 1h/4h only; E1 `up_bullish`/`up_bearish` grade A (origin in [12, 20]);
`down` (strength collapse) excluded; 2-of-3 confluence read on the SAME candle
the turn fired on (AO side-or-expanding / BBWP >50-or-rising / Konkorde marron
side, the Konkorde leg 4h-only); every entry `shadow: true, alertable: false`.

GOLDEN (spec, replay 2026-07-23): the BTC 1h turn the owner traded short —
E1 up_bearish fired on the candle closing 15:00Z with adx 22.3 / origin 15.9 /
grade A, AO -468.9, BBWP 57.9, Konkorde -123.8 -> fires "down". The negative
golden is the same day's 30m 21:00Z E1 `down` (origin 37.9): NO emission.
"""

import numpy as np
import pandas as pd

from controllers.metrics.monitors_v020 import (
    TURN_IGNITION_TFS,
    build_monitors_v020,
)

_FREQ = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "D", "1w": "7D"}

ENTRY_KEYS = {
    "timeframe", "direction", "variant", "grade", "origin_level", "age",
    "fire_candle_ts", "adx", "conditions", "confluence", "shadow", "alertable",
}

# E1 up-turn tail reproducing the golden fire on the LAST closed candle:
# base [-9..-5] flat ~15, leg start (origin) 15.9 at -4, steep leg to 22.3.
# slope_recent = (22.3-15.9)/3 = 2.13 >= 1.0; delta vs slope_prior 0.18 = 1.95
# >= 1.5; origin 15.9 in [12, 20] -> grade A.
_GOLDEN_ADX = np.array([15.0, 15.2, 15.4, 15.6, 15.8, 15.9, 18.0, 20.1, 22.3])
# Same shape from a HIGH origin (25.0 > 20) -> fires, but grade B.
_GRADE_B_ADX = np.array([24.5, 24.6, 24.7, 24.8, 24.9, 25.0, 27.1, 29.2, 31.4])
# E1 `down` collapse from origin 37.9 (golden negative, 30m 2026-07-23 21:00Z):
# slope_recent = -1.5 <= -1.0; slope_prior 0.1 - (-1.5) = 1.6 >= 1.5.
_DOWN_COLLAPSE_ADX = np.array([37.4, 37.5, 37.6, 37.7, 37.8, 37.9, 36.4, 34.9, 33.4])

_BEARISH_DI = {"plus": 12.0, "minus": 30.0}


def _frame(tf, n=60, *, end=None, ao=1.0, adx=20.0, plus=25.0, minus=15.0,
           bbwp=40.0, konkorde=5.0):
    """Enriched frame; scalar args may be arrays shaping the tail. `end` pins
    the LAST candle's OPEN time (candle close = open + tf duration)."""
    if end is not None:
        index = pd.date_range(end=end, periods=n, freq=_FREQ[tf], tz="UTC")
    else:
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


def _frames(**overrides):
    frames = {tf: _frame(tf) for tf in ("15m", "30m", "1h", "4h", "1d", "1w")}
    frames.update(overrides)
    return frames


def _build(frames):
    return build_monitors_v020(dict(frames), lambda tf: frames[tf])


def _ti(monitors):
    return monitors["turn_ignition"]


def test_rule_tfs_are_pinned_to_1h_and_4h():
    # Pre-registered spec: extending/shrinking the TF set invalidates the gate.
    assert TURN_IGNITION_TFS == ("1h", "4h")


def test_benign_frames_emit_the_key_and_no_entries():
    monitors = _build(_frames())
    assert monitors["turn_ignition"] == []


def test_golden_positive_btc_1h_20260723_1500z_fires_down():
    """Spec golden: BTC 1h 2026-07-23T15:00Z — adx 22.3 / origin 15.9 / grade A,
    AO -468.9 (side), BBWP 57.9 (>50), Konkorde -123.8 (recorded, N/A on 1h)."""
    frames = _frames(**{
        "1h": _frame(
            "1h", end="2026-07-23 14:00", adx=_GOLDEN_ADX,
            ao=-468.9, bbwp=57.9, konkorde=-123.8, **_BEARISH_DI,
        ),
    })
    entries = _ti(_build(frames))
    assert len(entries) == 1
    entry = entries[0]
    assert set(entry.keys()) == ENTRY_KEYS
    assert entry["timeframe"] == "1h"
    assert entry["direction"] == "down"
    assert entry["variant"] == "up_bearish"
    assert entry["grade"] == "A"
    assert entry["origin_level"] == 15.9
    assert entry["adx"] == 22.3
    assert entry["age"] == 0
    assert entry["fire_candle_ts"] == "2026-07-23T15:00:00+00:00"
    assert entry["shadow"] is True and entry["alertable"] is False

    conditions = entry["conditions"]
    assert conditions["ao"] == {
        "met": True, "value": -468.9, "sign_match": True, "expanding": False,
    }
    assert conditions["bbwp"] == {
        "met": True, "value": 57.9, "above_50": True, "rising": False,
    }
    # Konkorde: the LEG does not apply on 1h (never counts), value recorded.
    assert conditions["konkorde"] == {"applies": False, "met": None, "value": -123.8}
    assert entry["confluence"] == {"met": 2, "required": 2}


def test_golden_negative_30m_down_collapse_never_fires():
    """Spec golden negative: 30m 2026-07-23 21:00Z E1 `down` (origin 37.9) with
    side AO / high BBWP still emits NOTHING — 30m is not a rule TF, and the
    `down` variant (strength collapse) is excluded by design."""
    frames = _frames(**{
        "30m": _frame(
            "30m", end="2026-07-23 20:30", adx=_DOWN_COLLAPSE_ADX,
            ao=-500.0, bbwp=60.0, **_BEARISH_DI,
        ),
    })
    assert _ti(_build(frames)) == []
    assert "30m" not in TURN_IGNITION_TFS


def test_down_variant_excluded_even_on_a_rule_tf():
    # The same collapse tail ON 1h: still nothing (variant gate, not TF gate).
    frames = _frames(**{
        "1h": _frame("1h", adx=_DOWN_COLLAPSE_ADX, ao=-500.0, bbwp=60.0,
                     **_BEARISH_DI),
    })
    assert _ti(_build(frames)) == []


def test_grade_b_origin_excluded():
    # Fires up_bearish but from origin 25.0 (> 20) -> grade B -> no emission.
    frames = _frames(**{
        "1h": _frame("1h", adx=_GRADE_B_ADX, ao=-500.0, bbwp=60.0, **_BEARISH_DI),
    })
    assert _ti(_build(frames)) == []


def test_confluence_below_two_suppresses_the_fire():
    # Grade-A fire, but AO on the WRONG side (flat, not expanding) and BBWP
    # low/flat -> 0 of 2 on 1h -> nothing.
    frames = _frames(**{
        "1h": _frame("1h", adx=_GOLDEN_ADX, ao=500.0, bbwp=40.0, **_BEARISH_DI),
    })
    assert _ti(_build(frames)) == []


def test_konkorde_leg_counts_on_4h_only():
    # AO wrong-side flat (a: no), BBWP 57.9 (b: yes), Konkorde on the side
    # (c: yes on 4h) -> 2 of 3 fires on 4h; the same inputs on 1h are 1 of 2.
    kwargs = dict(adx=_GOLDEN_ADX, ao=500.0, bbwp=57.9, konkorde=-123.8,
                  **_BEARISH_DI)
    fired = _ti(_build(_frames(**{"4h": _frame("4h", **kwargs)})))
    assert len(fired) == 1
    entry = fired[0]
    assert entry["timeframe"] == "4h" and entry["direction"] == "down"
    assert entry["conditions"]["ao"]["met"] is False
    assert entry["conditions"]["konkorde"] == {
        "applies": True, "met": True, "value": -123.8,
    }
    assert entry["confluence"] == {"met": 2, "required": 2}

    assert _ti(_build(_frames(**{"1h": _frame("1h", **kwargs)}))) == []


def test_ao_expanding_and_bbwp_rising_alternate_paths():
    # (a) via |AO| expanding >= 2 candles (wrong side!) and (b) via BBWP
    # rising >= 2 closes while still under 50 — the OR legs of the spec.
    frames = _frames(**{
        "1h": _frame(
            "1h", adx=_GOLDEN_ADX,
            ao=np.array([100.0, 120.0, 150.0]),
            bbwp=np.array([44.0, 46.0, 48.0]),
            **_BEARISH_DI,
        ),
    })
    entries = _ti(_build(frames))
    assert len(entries) == 1
    conditions = entries[0]["conditions"]
    assert conditions["ao"] == {
        "met": True, "value": 150.0, "sign_match": False, "expanding": True,
    }
    assert conditions["bbwp"] == {
        "met": True, "value": 48.0, "above_50": False, "rising": True,
    }


def test_identity_is_the_fire_candle_one_candle_later():
    """One candle after the golden fire (which itself does not re-fire), the
    entry re-emits with age 1 and the SAME fire_candle_ts — the consumer's
    dedup key stays stable, making the emission one-shot per candle."""
    adx = np.append(_GOLDEN_ADX, 22.4)  # next candle: slope delta 0.91 < 1.5
    frames = _frames(**{
        "1h": _frame("1h", end="2026-07-23 15:00", adx=adx,
                     ao=-468.9, bbwp=57.9, **_BEARISH_DI),
    })
    entries = _ti(_build(frames))
    assert len(entries) == 1
    assert entries[0]["age"] == 1
    assert entries[0]["fire_candle_ts"] == "2026-07-23T15:00:00+00:00"


def test_up_direction_requires_bullish_di_and_positive_ao():
    # Mirror sanity: bullish DI colours the same grade-A turn "up"; AO must be
    # POSITIVE for the side match.
    frames = _frames(**{
        "1h": _frame("1h", adx=_GOLDEN_ADX, ao=468.9, bbwp=57.9,
                     plus=30.0, minus=12.0),
    })
    entries = _ti(_build(frames))
    assert len(entries) == 1
    assert entries[0]["direction"] == "up"
    assert entries[0]["variant"] == "up_bullish"
    assert entries[0]["conditions"]["ao"]["sign_match"] is True
