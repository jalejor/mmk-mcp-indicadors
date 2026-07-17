"""Trend Speed Analyzer — bar-exact port of Zeiierman's TradingView indicator.

Attribution: © Zeiierman — "Trend Speed Analyzer (Zeiierman)" (TradingView,
Pine Script v6). Licensed CC BY-NC-SA 4.0
(https://creativecommons.org/licenses/by-nc-sa/4.0/). This port lives in a
PRIVATE repository for personal, non-commercial use, keeps this attribution,
and is itself shared under the same license terms. If mmk is ever
commercialised this module must be replaced.

What it computes (per closed candle, float64, Pine warmup NaN included):

* Dynamic EMA: length adapts between 5 and `max_length` from close
  normalised against `highest(abs(close), 200)`; the smoothing alpha is
  boosted by an acceleration factor (|delta close| normalised against
  `highest(|delta close|, 200)`) times `accel_multiplier`, capped at 1.
  Seed: first bar (or any bar after the previous dyn_ema is na) restarts at
  `close` — during the first 200 bars alpha is na, so the seed/na
  alternation of the Pine warmup is replicated verbatim.
* Waves: a wave runs between consecutive crosses of `close` over/under the
  dynamic EMA (cross test compares close[1] against the CURRENT dyn_ema,
  exactly as the Pine does). On a bullish cross the closing bearish wave
  records `lowest(speed, bar_index - x1)`; on a bearish cross the bullish
  wave records `highest(speed, bar_index - x1)` (variable window length,
  clamped to >= 1 because Pine rejects length 0). Pine series semantics:
  at that point of the script `speed` still holds the PREVIOUS bar's value,
  so the window covers end-of-bar values `[i-N+1, i-1]`.
* Speed: RMA(close,10) - RMA(open,10) accumulated within the wave. On a
  cross bar the accumulator RESETS to `c - o` (no double count — verified
  against two independent conversions of the original, ThinkScript and
  ProRealTime); on any other bar `speed := speed + (c - o)`. Pine's
  `ta.rma` is Wilder smoothing: SMA(len) seed, then
  `alpha=1/len` recursion — na for the first `len-1` bars.
* trend_speed = HMA(speed, 5) = WMA(2*WMA(x,2) - WMA(x,5), 2) — the
  histogram series the owner sees.
* Table stats over the last `lookback_period` waves per side: avg/extreme
  wave, current-wave ratios and dominance (see `_stats`).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

import numpy as np
import pandas as pd

DEFAULT_MAX_LENGTH = 50
DEFAULT_ACCEL_MULTIPLIER = 5.0
DEFAULT_LOOKBACK_PERIOD = 100  # waves kept per side for the table stats
_NORM_LEN = 200  # Pine: ta.highest(..., 200) for both normalisations
_RMA_LEN = 10
_HMA_LEN = 5
_MIN_DYN_LENGTH = 5.0


@dataclass
class TrendSpeedResult:
    """Series + wave stats produced by `trend_speed_analyzer`."""

    frame: pd.DataFrame  # columns: dyn_ema, speed, trend_speed, wave_dir
    stats: Dict[str, Any]
    bullish_waves: List[float] = field(default_factory=list)  # newest first
    bearish_waves: List[float] = field(default_factory=list)  # newest first


def pine_rma(values: np.ndarray, length: int) -> np.ndarray:
    """Pine `ta.rma` (Wilder): na until `length-1`, SMA seed, alpha=1/len."""
    n = len(values)
    out = np.full(n, np.nan)
    if n < length:
        return out
    out[length - 1] = float(np.mean(values[:length]))
    alpha = 1.0 / length
    for i in range(length, n):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def pine_wma(values: np.ndarray, length: int) -> np.ndarray:
    """Pine `ta.wma`: linear weights (most recent = `length`), na-strict."""
    n = len(values)
    out = np.full(n, np.nan)
    weights = np.arange(1, length + 1, dtype="float64")
    denominator = weights.sum()
    for i in range(length - 1, n):
        window = values[i - length + 1: i + 1]
        if np.isnan(window).any():
            continue
        out[i] = float(np.dot(window, weights) / denominator)
    return out


def pine_hma(values: np.ndarray, length: int) -> np.ndarray:
    """Pine `ta.hma`: WMA(2*WMA(x, len/2) - WMA(x, len), round(sqrt(len)))."""
    half = pine_wma(values, max(1, length // 2))
    full = pine_wma(values, length)
    return pine_wma(2.0 * half - full, max(1, round(math.sqrt(length))))


def _rolling_highest(values: np.ndarray, length: int) -> np.ndarray:
    """Pine `ta.highest`: na until the window is full."""
    return (
        pd.Series(values)
        .rolling(length)
        .max()
        .to_numpy(dtype="float64")
    )


def _wave_extreme(speed_hist: List[float], i: int, window_len: int, *, kind: str) -> float:
    """Pine `ta.highest/lowest(speed, N)` at bar `i`, before `speed` updates.

    At that line `speed` still carries the end-of-bar `i-1` value, so the
    N-offsets window collapses to the end-of-bar values `[i-N+1, i-1]`
    (offset 0 duplicates `speed_hist[i-1]`). na-strict like Pine.
    """
    window = speed_hist[max(0, i - window_len + 1): i] or [speed_hist[i - 1]]
    if any(math.isnan(v) for v in window):
        return math.nan
    return max(window) if kind == "highest" else min(window)


def trend_speed_analyzer(
    open_: pd.Series,
    close: pd.Series,
    *,
    max_length: int = DEFAULT_MAX_LENGTH,
    accel_multiplier: float = DEFAULT_ACCEL_MULTIPLIER,
    lookback_period: int = DEFAULT_LOOKBACK_PERIOD,
) -> TrendSpeedResult:
    """Run the full Trend Speed Analyzer over aligned open/close series.

    Pure function (inputs never mutated). Bar-exact against the Pine,
    including the na warmup of the first ~200 bars: `speed` stays na until
    the first close/dyn_ema cross resets it — on a chart with long history
    (the owner's case) this warmup is invisible.
    """
    if len(open_) != len(close):
        raise ValueError("open_ and close must have the same length")

    closes = close.to_numpy(dtype="float64")
    opens = open_.to_numpy(dtype="float64")
    n = len(closes)
    if n == 0:
        empty = pd.DataFrame(
            {"dyn_ema": [], "speed": [], "trend_speed": [], "wave_dir": []},
            index=close.index,
        )
        return TrendSpeedResult(frame=empty, stats=_stats(
            speed=math.nan, bullish_change=[], bearish_change=[], bullish_t=[], bearish_t=[],
        ))

    alpha = _dyn_alpha(closes, max_length=max_length, accel_multiplier=accel_multiplier)
    c = pine_rma(closes, _RMA_LEN)
    o = pine_rma(opens, _RMA_LEN)

    dyn_ema = np.full(n, np.nan)
    speed_hist: List[float] = []
    wave_dir = np.zeros(n, dtype="int64")
    bullish_change: Deque[float] = deque(maxlen=lookback_period)
    bearish_change: Deque[float] = deque(maxlen=lookback_period)
    bullish_t: Deque[int] = deque(maxlen=lookback_period)
    bearish_t: Deque[int] = deque(maxlen=lookback_period)

    x1 = 0  # Pine: `if na(x1): x1 := bar_index` fires on the first bar
    pos = 0
    speed = 0.0  # Pine: `var speed = 0.0`

    for i in range(n):
        # -- dynamic EMA (na alpha replicates the Pine warmup verbatim) ----
        if i == 0 or math.isnan(dyn_ema[i - 1]):
            dyn_ema[i] = closes[i]
        else:
            dyn_ema[i] = alpha[i] * closes[i] + (1.0 - alpha[i]) * dyn_ema[i - 1]

        # -- crosses of close over/under the CURRENT dyn_ema ---------------
        crossed_up = i >= 1 and closes[i] > dyn_ema[i] and closes[i - 1] <= dyn_ema[i]
        crossed_down = i >= 1 and closes[i] < dyn_ema[i] and closes[i - 1] >= dyn_ema[i]
        bar_delta = c[i] - o[i]

        if crossed_up:
            window_len = max(1, i - x1)
            bearish_change.appendleft(_wave_extreme(speed_hist, i, window_len, kind="lowest"))
            bearish_t.appendleft(i - x1)
            x1, pos, speed = i, 1, bar_delta
        elif crossed_down:
            window_len = max(1, i - x1)
            bullish_change.appendleft(_wave_extreme(speed_hist, i, window_len, kind="highest"))
            bullish_t.appendleft(i - x1)
            x1, pos, speed = i, -1, bar_delta
        else:
            speed = speed + bar_delta

        speed_hist.append(speed)
        wave_dir[i] = pos

    speed_arr = np.array(speed_hist, dtype="float64")
    frame = pd.DataFrame(
        {
            "dyn_ema": dyn_ema,
            "speed": speed_arr,
            "trend_speed": pine_hma(speed_arr, _HMA_LEN),
            "wave_dir": wave_dir,
        },
        index=close.index,
    )
    stats = _stats(
        speed=speed_hist[-1] if speed_hist else math.nan,
        bullish_change=list(bullish_change),
        bearish_change=list(bearish_change),
        bullish_t=list(bullish_t),
        bearish_t=list(bearish_t),
    )
    return TrendSpeedResult(
        frame=frame,
        stats=stats,
        bullish_waves=list(bullish_change),
        bearish_waves=list(bearish_change),
    )


def _dyn_alpha(closes: np.ndarray, *, max_length: int, accel_multiplier: float) -> np.ndarray:
    """Per-bar smoothing alpha of the dynamic EMA (na during warmup)."""
    counts_diff = closes  # Pine: counts_diff = close
    max_abs = _rolling_highest(np.abs(counts_diff), _NORM_LEN)
    norm = (counts_diff + max_abs) / (2.0 * max_abs)
    dyn_length = _MIN_DYN_LENGTH + norm * (max_length - _MIN_DYN_LENGTH)

    delta = np.abs(counts_diff - np.concatenate(([0.0], counts_diff[:-1])))  # nz(close[1])
    max_delta = _rolling_highest(delta, _NORM_LEN)
    # Pine: `max_delta := max_delta == 0 ? 1 : max_delta` — na stays na.
    max_delta = np.where(max_delta == 0.0, 1.0, max_delta)
    accel_factor = delta / max_delta

    return np.minimum(1.0, (2.0 / (dyn_length + 1.0)) * (1.0 + accel_factor * accel_multiplier))


def _mean(values: List[float]) -> Optional[float]:
    clean = [v for v in values if not math.isnan(v)]
    return float(np.mean(clean)) if clean else None


def _extreme(values: List[float], picker) -> Optional[float]:
    clean = [v for v in values if not math.isnan(v)]
    return float(picker(clean)) if clean else None


def _stats(
    *,
    speed: float,
    bullish_change: List[float],
    bearish_change: List[float],
    bullish_t: List[int],
    bearish_t: List[int],
) -> Dict[str, Any]:
    """Table stats over the stored waves (newest first, capped per side).

    NaN wave records (only possible while the Pine warmup is still inside
    the window) are skipped — on long history they aged out long ago.
    """
    bull_avg = _mean(bullish_change)
    bull_max = _extreme(bullish_change, max)
    bear_avg = _mean(bearish_change)
    bear_min = _extreme(bearish_change, min)

    current_ratio_avg = None
    current_ratio_max = None
    if not math.isnan(speed):
        if speed > 0:
            current_ratio_avg = speed / bull_avg if bull_avg else None
            current_ratio_max = speed / bull_max if bull_max else None
        else:
            current_ratio_avg = speed / abs(bear_avg) if bear_avg else None
            current_ratio_max = speed / abs(bear_min) if bear_min else None

    dominance_avg = bull_avg - abs(bear_avg) if bull_avg is not None and bear_avg is not None else None
    dominance_max = bull_max - abs(bear_min) if bull_max is not None and bear_min is not None else None

    return {
        "speed": None if math.isnan(speed) else float(speed),
        "bull_avg": bull_avg,
        "bull_max": bull_max,
        "bear_avg": bear_avg,
        "bear_min": bear_min,
        "current_ratio_avg": current_ratio_avg,
        "current_ratio_max": current_ratio_max,
        "dominance_avg": dominance_avg,
        "dominance_max": dominance_max,
        "bull_wave_count": len(bullish_change),
        "bear_wave_count": len(bearish_change),
        "bull_avg_duration": _mean([float(t) for t in bullish_t]),
        "bear_avg_duration": _mean([float(t) for t in bearish_t]),
    }
