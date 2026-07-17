"""Bollinger Band Width Percentile — exact port of The_Caretaker's `f_bbwp`.

Derived work of the TradingView indicator "Bollinger Band Width Percentile"
by The_Caretaker (Pine Script v6). Original source licensed under the
Mozilla Public License 2.0 — https://mozilla.org/MPL/2.0/ — this notice and
the license are preserved in this derived file.

This is the OWNER-CALIBRATED variant (`bbwp_owner`) exposed ALONGSIDE the
engine's legacy `bbwp` (`IndicatorsService._calc_bbwp`); it does NOT replace
it — historical readings and the active rules keep consuming the legacy one.
Owner chart settings: basis SMA(13), lookback 256, SMA(5) over the BBWP,
extreme thresholds 98 / 2.

Pine semantics replicated bar-by-bar (float64, warmup NaN included):

* BBW = 2 * stdev_population(close, basis_len) / SMA(close, basis_len)
  — Pine's `ta.stdev` is population (ddof=0); ((Upper-Lower)/Basis) with
  2-sigma bands reduces to this expression.
* Output gate: `bar_index >= basis_len` (0-based). The first valid BBW
  (bar `basis_len - 1`) is neither ranked nor buffered — exactly like the
  Pine, whose `if bar_index >= _bbwLen` skips it.
* Percentile = count of buffered PREVIOUS values `<=` current BBW
  (`array.binary_search_rightmost` == `bisect_right`) * 100 / buffer size.
  The current value is ranked BEFORE being inserted into the buffer.
* Dynamic window: the buffer grows one value per bar up to `lookback`
  previous values, then slides (oldest evicted). Output therefore starts as
  soon as `bar_index == basis_len + 1` — it does NOT wait for a full
  lookback (this is the calibration difference vs the engine's `bbwp`).
* First evaluation (`bar_index == basis_len`): empty buffer -> Pine divides
  by zero -> na. Replicated as NaN.
* Tie edge (documented divergence): on an EXACT float match Pine's
  `binary_search_rightmost` returns the last-occurrence index (one less
  than `bisect_right`). Exact ties have measure zero on real price data and
  the owner-annotated semantics ("count <=") dictate `bisect_right`, so
  `bisect_right` wins here.
"""

from __future__ import annotations

import math
from bisect import bisect_right, insort_right
from collections import deque
from typing import Deque, List

import pandas as pd

# Owner chart calibration (2026-07-16).
DEFAULT_BASIS_LEN = 13
DEFAULT_LOOKBACK = 256
DEFAULT_MA_LEN = 5
EXTREME_HIGH = 98.0
EXTREME_LOW = 2.0


def bbwp_owner_series(
    close: pd.Series,
    *,
    basis_len: int = DEFAULT_BASIS_LEN,
    lookback: int = DEFAULT_LOOKBACK,
    ma_len: int = DEFAULT_MA_LEN,
) -> pd.DataFrame:
    """Compute the owner-calibrated BBW / BBWP / BBWP-MA series.

    Pure function: `close` is never mutated. Returns a DataFrame aligned to
    `close.index` with float64 columns `bbw`, `bbwp` and `bbwp_ma` (leading
    NaN during warmup, exactly as the Pine plots).
    """
    if basis_len < 1 or lookback < 1 or ma_len < 1:
        raise ValueError("basis_len, lookback and ma_len must be >= 1")

    values = close.astype("float64")
    basis = values.rolling(basis_len).mean()
    stdev = values.rolling(basis_len).std(ddof=0)  # Pine ta.stdev = population
    bbw = 2.0 * stdev / basis

    bbwp: List[float] = [math.nan] * len(values)
    raw_values: Deque[float] = deque()
    sorted_values: List[float] = []

    for i, current in enumerate(bbw.to_numpy(dtype="float64")):
        if i < basis_len:
            continue  # Pine: `if bar_index >= _bbwLen` — before it, BBWP stays na
        if math.isnan(current):
            # Unreachable with real prices (basis/stdev are valid past warmup
            # and prices are > 0); guarded so a degenerate series cannot
            # poison the buffer.
            continue
        size = len(sorted_values)
        if size > 0:
            bbwp[i] = bisect_right(sorted_values, current) * 100.0 / size
        # else: Pine divides by array.size == 0 -> na. Keep NaN.
        raw_values.append(current)
        insort_right(sorted_values, current)
        if len(raw_values) > lookback:
            oldest = raw_values.popleft()
            # Pine removes the rightmost occurrence of the evicted value.
            del sorted_values[bisect_right(sorted_values, oldest) - 1]

    bbwp_series = pd.Series(bbwp, index=values.index, dtype="float64")
    # Pine `ta.sma` over a series with na in the window yields na — pandas'
    # default rolling(min_periods=window) matches.
    bbwp_ma = bbwp_series.rolling(ma_len).mean()

    return pd.DataFrame(
        {"bbw": bbw, "bbwp": bbwp_series, "bbwp_ma": bbwp_ma},
        index=values.index,
    )
