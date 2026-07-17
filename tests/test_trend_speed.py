"""Goldens for the Trend Speed Analyzer port (Zeiierman, CC BY-NC-SA 4.0).

Pins the Pine building blocks (`ta.rma` Wilder seed, `ta.wma`/`ta.hma`
composition, `ta.highest` warmup), the dynamic-EMA warmup behaviour, and the
wave/speed bookkeeping invariants recomputed independently in the test.
"""

import math

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.trend_speed import (
    pine_hma,
    pine_rma,
    pine_wma,
    trend_speed_analyzer,
)


def _ohlc(n: int, seed: int = 21, drift: float = 0.0):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(100.0 + np.cumsum(rng.normal(drift, 0.7, size=n)), index=index)
    open_ = close.shift(1).fillna(close.iloc[0]) + rng.normal(0, 0.1, size=n)
    return open_, close


# ---------------------------------------------------------------------------
# Pine building blocks
# ---------------------------------------------------------------------------

def test_pine_rma_wilder_seed_and_recursion():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype="float64")
    out = pine_rma(values, 3)
    assert np.isnan(out[:2]).all()          # na for the first len-1 bars
    assert out[2] == pytest.approx(2.0)     # seed = SMA of the first 3
    assert out[3] == pytest.approx((1 / 3) * 4.0 + (2 / 3) * 2.0)
    assert out[4] == pytest.approx((1 / 3) * 5.0 + (2 / 3) * out[3])


def test_pine_wma_linear_weights():
    values = np.array([3.0, 2.0, 1.0, 4.0], dtype="float64")
    out = pine_wma(values, 3)
    assert np.isnan(out[:2]).all()
    # weights 1,2,3 (most recent = 3): (3*1 + 2*2 + 1*3)/6
    assert out[2] == pytest.approx((3.0 * 1 + 2.0 * 2 + 1.0 * 3) / 6.0)
    assert out[3] == pytest.approx((2.0 * 1 + 1.0 * 2 + 4.0 * 3) / 6.0)


def test_pine_hma_composition():
    rng = np.random.default_rng(5)
    values = np.cumsum(rng.normal(0, 1, 40))
    expected = pine_wma(2.0 * pine_wma(values, 2) - pine_wma(values, 5), 2)
    out = pine_hma(values, 5)
    assert np.allclose(out[6:], expected[6:], rtol=0, atol=1e-12)
    assert np.isnan(out[:5]).all()  # wma(5) na until bar 4, hma adds one more


# ---------------------------------------------------------------------------
# Dynamic EMA warmup (bar-exact Pine semantics)
# ---------------------------------------------------------------------------

def test_dyn_ema_warmup_alternates_then_stabilises():
    """Before bar 200 alpha is na (highest(.,200) not full): the Pine seeds
    dyn_ema at `close`, poisons it to na the next bar, reseeds, ... From bar
    199 on, alpha is valid and dyn_ema is a real adaptive EMA (never na)."""
    open_, close = _ohlc(260)
    result = trend_speed_analyzer(open_, close)
    dyn = result.frame["dyn_ema"]

    assert dyn.iloc[0] == close.iloc[0]           # seed
    assert math.isnan(dyn.iloc[1])                # na alpha poisons
    assert dyn.iloc[2] == close.iloc[2]           # reseed
    assert dyn.iloc[199:].notna().all()           # stable once alpha exists
    # ... and it is a genuine blend, not the raw close.
    assert (dyn.iloc[200:] != close.iloc[200:]).any()


def test_speed_stays_nan_until_first_cross_then_resets_and_accumulates():
    """Pine: `var speed = 0.0` plus na (c - o) during the RMA warmup poisons
    the accumulator until the FIRST cross resets it to c - o; afterwards it
    accumulates c - o every non-cross bar. Recomputed independently here."""
    open_, close = _ohlc(400, seed=3)
    result = trend_speed_analyzer(open_, close)
    frame = result.frame

    closes = close.to_numpy()
    dyn = frame["dyn_ema"].to_numpy()

    def _is_cross(i):
        up = closes[i] > dyn[i] and closes[i - 1] <= dyn[i]
        down = closes[i] < dyn[i] and closes[i - 1] >= dyn[i]
        return up or down

    crosses = [i for i in range(1, len(closes)) if _is_cross(i)]
    assert crosses, "seeded walk must cross its dynamic EMA at least once"
    first_cross = crosses[0]
    assert first_cross >= 199  # warmup dyn_ema alternation admits no cross

    speed = frame["speed"]
    c = pine_rma(closes, 10)
    o = pine_rma(open_.to_numpy(), 10)
    assert speed.iloc[:first_cross].isna().all()
    assert speed.iloc[first_cross] == pytest.approx(c[first_cross] - o[first_cross])
    for i in range(first_cross + 1, len(closes)):
        expected = (
            c[i] - o[i] if i in crosses            # reset on the cross bar
            else speed.iloc[i - 1] + (c[i] - o[i])  # accumulate otherwise
        )
        assert speed.iloc[i] == pytest.approx(expected), f"bar {i}"


def test_wave_dir_flips_exactly_on_crosses():
    open_, close = _ohlc(400, seed=3)
    result = trend_speed_analyzer(open_, close)
    frame = result.frame
    closes = close.to_numpy()
    dyn = frame["dyn_ema"].to_numpy()

    pos = 0
    for i in range(len(closes)):
        if i >= 1 and closes[i] > dyn[i] and closes[i - 1] <= dyn[i]:
            pos = 1
        elif i >= 1 and closes[i] < dyn[i] and closes[i - 1] >= dyn[i]:
            pos = -1
        assert frame["wave_dir"].iloc[i] == pos, f"bar {i}"


def test_trendspeed_is_hma5_of_speed():
    open_, close = _ohlc(400, seed=8)
    result = trend_speed_analyzer(open_, close)
    expected = pine_hma(result.frame["speed"].to_numpy(dtype="float64"), 5)
    got = result.frame["trend_speed"].to_numpy(dtype="float64")
    assert np.allclose(got, expected, rtol=0, atol=1e-12, equal_nan=True)


# ---------------------------------------------------------------------------
# Wave records + table stats
# ---------------------------------------------------------------------------

def test_wave_records_and_stats_recomputed_independently():
    open_, close = _ohlc(700, seed=13)
    result = trend_speed_analyzer(open_, close, lookback_period=100)
    frame = result.frame

    closes = close.to_numpy()
    dyn = frame["dyn_ema"].to_numpy()
    speed_hist = frame["speed"].to_numpy()

    bull, bear = [], []
    x1 = 0
    for i in range(1, len(closes)):
        up = closes[i] > dyn[i] and closes[i - 1] <= dyn[i]
        down = closes[i] < dyn[i] and closes[i - 1] >= dyn[i]
        if not (up or down):
            continue
        window_len = max(1, i - x1)
        window = speed_hist[max(0, i - window_len + 1): i]
        window = window if window.size else speed_hist[i - 1: i]
        extreme = (
            math.nan if np.isnan(window).any()
            else (float(window.min()) if up else float(window.max()))
        )
        (bear if up else bull).insert(0, extreme)
        x1 = i
    bull, bear = bull[:100], bear[:100]

    assert result.bullish_waves == pytest.approx(bull, nan_ok=True)
    assert result.bearish_waves == pytest.approx(bear, nan_ok=True)

    clean_bull = [v for v in bull if not math.isnan(v)]
    clean_bear = [v for v in bear if not math.isnan(v)]
    assert clean_bull and clean_bear, "seeded walk must close waves on both sides"
    stats = result.stats
    assert stats["bull_avg"] == pytest.approx(np.mean(clean_bull))
    assert stats["bull_max"] == pytest.approx(max(clean_bull))
    assert stats["bear_avg"] == pytest.approx(np.mean(clean_bear))
    assert stats["bear_min"] == pytest.approx(min(clean_bear))
    assert stats["dominance_avg"] == pytest.approx(
        np.mean(clean_bull) - abs(np.mean(clean_bear))
    )
    assert stats["dominance_max"] == pytest.approx(max(clean_bull) - abs(min(clean_bear)))

    last_speed = float(frame["speed"].iloc[-1])
    if last_speed > 0:
        assert stats["current_ratio_avg"] == pytest.approx(last_speed / np.mean(clean_bull))
    else:
        assert stats["current_ratio_avg"] == pytest.approx(last_speed / abs(np.mean(clean_bear)))


def test_stats_are_json_safe_none_not_nan():
    open_, close = _ohlc(50)  # far too short: everything stays na / empty
    stats = trend_speed_analyzer(open_, close).stats
    for key, value in stats.items():
        assert value is None or isinstance(value, (int, float)), key
        if isinstance(value, float):
            assert not math.isnan(value), key


def test_empty_input_returns_empty_result():
    empty = pd.Series([], dtype="float64")
    result = trend_speed_analyzer(empty, empty)
    assert result.frame.empty
    assert result.stats["bull_wave_count"] == 0
