"""Goldens for the owner-calibrated BBWP port (The_Caretaker `f_bbwp`).

Three layers:

1. Parity of the O(n log n) implementation against a literal, naive O(n^2)
   re-reading of the Pine (window rebuilt per bar), on synthetic AND real
   candles — any drift in buffer/gate/percentile semantics breaks this.
2. Pine semantics pinned bar-by-bar on hand-checkable series (gate at
   `bar_index >= basis_len`, empty-buffer NaN, compare-before-insert,
   dynamic window, extremes -> 0/100, MA5 warmup).
3. Q19 in numbers: on the SAME real candles the engine's legacy `bbwp`
   (basis 20, lookback 252, rank includes the current bar) and the owner's
   chart BBWP (basis 13, lookback 256, previous-values-only) are materially
   different series — which is why engine-vs-chart comparisons were invalid
   until this variant existed.
"""

import json
import math
import pathlib

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.bbwp_owner import (
    DEFAULT_BASIS_LEN,
    DEFAULT_LOOKBACK,
    DEFAULT_MA_LEN,
    bbwp_owner_series,
)
from controllers.metrics.indicators_service import IndicatorsService

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _fixture_ohlcv(timeframe: str) -> pd.DataFrame:
    raw = json.loads((FIXTURES / f"btc_usdt_bitget_{timeframe}_20260713T1600.json").read_text())
    frame = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame.index = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame


def _naive_bbwp(close: pd.Series, basis_len: int, lookback: int) -> pd.Series:
    """Literal O(n^2) re-reading of the Pine, kept independent on purpose.

    For every bar past the gate, the comparison window is rebuilt from
    scratch: the BBW values of bars `[max(basis_len, i - lookback), i)` —
    i.e. every PREVIOUS pushed value, capped at `lookback`.
    """
    basis = close.rolling(basis_len).mean()
    stdev = close.rolling(basis_len).std(ddof=0)
    bbw = (2.0 * stdev / basis).to_numpy(dtype="float64")

    out = np.full(len(bbw), np.nan)
    for i in range(basis_len, len(bbw)):
        window = bbw[max(basis_len, i - lookback): i]
        if window.size == 0 or math.isnan(bbw[i]):
            continue
        out[i] = np.count_nonzero(window <= bbw[i]) * 100.0 / window.size
    return pd.Series(out, index=close.index)


def _random_walk_close(n: int, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2026-01-01", periods=n, freq="4h", tz="UTC")
    return pd.Series(100.0 + np.cumsum(rng.normal(0, 0.8, size=n)), index=index)


# ---------------------------------------------------------------------------
# 1. Fast implementation == naive Pine re-reading
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_parity_fast_vs_naive_synthetic(seed):
    close = _random_walk_close(600, seed)  # > basis_len + lookback: window slides
    fast = bbwp_owner_series(close)["bbwp"]
    naive = _naive_bbwp(close, DEFAULT_BASIS_LEN, DEFAULT_LOOKBACK)
    pd.testing.assert_series_equal(fast, naive, check_names=False, rtol=0, atol=1e-9)


@pytest.mark.parametrize("timeframe", ["4h", "1h"])
def test_parity_fast_vs_naive_real_candles(timeframe):
    close = _fixture_ohlcv(timeframe)["close"]
    fast = bbwp_owner_series(close)["bbwp"]
    naive = _naive_bbwp(close, DEFAULT_BASIS_LEN, DEFAULT_LOOKBACK)
    pd.testing.assert_series_equal(fast, naive, check_names=False, rtol=0, atol=1e-9)


def test_parity_holds_with_small_lookback_ties_and_eviction():
    """Repeated values force exact-tie inserts/evictions through the sorted
    buffer; a tiny lookback exercises the sliding window heavily."""
    values = [100.0, 101.0, 100.0, 101.0, 102.0, 100.0, 101.0, 102.0] * 12
    index = pd.date_range("2026-01-01", periods=len(values), freq="h", tz="UTC")
    close = pd.Series(values, index=index, dtype="float64")
    fast = bbwp_owner_series(close, basis_len=5, lookback=7)["bbwp"]
    naive = _naive_bbwp(close, 5, 7)
    pd.testing.assert_series_equal(fast, naive, check_names=False, rtol=0, atol=1e-9)


# ---------------------------------------------------------------------------
# 2. Pine semantics, hand-checkable
# ---------------------------------------------------------------------------

def test_warmup_gate_and_first_evaluation_nan():
    """No output before `bar_index = basis_len + 1`: bars < basis_len-1 have
    no BBW; bar basis_len-1 is skipped by the gate (never ranked NOR
    buffered); bar basis_len ranks against an EMPTY buffer -> Pine division
    by zero -> NaN. First real value lands on bar basis_len + 1."""
    close = _random_walk_close(60, seed=9)
    result = bbwp_owner_series(close, basis_len=13, lookback=256)
    assert result["bbwp"].iloc[: 13 + 1].isna().all()
    assert not math.isnan(result["bbwp"].iloc[14])


def test_current_value_ranked_against_previous_only():
    """A monotonically expanding BBW must print 100 from the first valid bar
    (every previous value is <= the current one), and a collapsing one 0 —
    the current value never ranks against itself."""
    n = 80
    index = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    # Exponential close growth => strictly expanding stdev/basis ratio.
    expanding = pd.Series(100.0 * np.exp(np.arange(n) * np.linspace(0.001, 0.05, n)), index=index)
    result = bbwp_owner_series(expanding, basis_len=13, lookback=256)["bbwp"]
    valid = result.dropna()
    assert not valid.empty
    assert (valid == 100.0).all()


def test_dynamic_window_before_lookback_is_full():
    """With basis 5 / lookback 100 and only 12 bars, bar i ranks against
    exactly i - 5 previous values — output exists long before the lookback
    fills (the calibration difference vs the engine's min_periods=1 rank
    over its own 252 window)."""
    close = pd.Series(
        [100, 101, 99, 102, 98, 103, 97, 104, 96, 105, 95, 106],
        index=pd.date_range("2026-01-01", periods=12, freq="h", tz="UTC"),
        dtype="float64",
    )
    result = bbwp_owner_series(close, basis_len=5, lookback=100)["bbwp"]
    naive = _naive_bbwp(close, 5, 100)
    pd.testing.assert_series_equal(result, naive, check_names=False, rtol=0, atol=1e-9)
    assert result.iloc[6:].notna().all()  # ranked from bar 6 (buffer size 1)


def test_ma5_is_sma_over_bbwp_with_pine_na_poisoning():
    close = _random_walk_close(400, seed=11)
    result = bbwp_owner_series(close)
    expected = result["bbwp"].rolling(DEFAULT_MA_LEN).mean()
    pd.testing.assert_series_equal(result["bbwp_ma"], expected, check_names=False)


def test_invalid_params_rejected():
    close = _random_walk_close(50, seed=1)
    with pytest.raises(ValueError):
        bbwp_owner_series(close, basis_len=0)


# ---------------------------------------------------------------------------
# 3. Q19 in numbers: engine bbwp != owner bbwp on the same candles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("timeframe", ["4h", "1h"])
def test_q19_engine_and_owner_bbwp_are_materially_different(timeframe):
    """Same candles, both 'BBWP', materially different series.

    Engine: BBW from 20/2 bands, percentile = pct-rank INCLUDING the
    current bar over a min_periods=1 rolling 252 window. Owner chart:
    BBW from SMA(13) population stdev, percentile = share of the previous
    <=256 buffered values <= current. This is Q19: comparisons between the
    engine's readings and the owner's chart are invalid until made on the
    SAME definition (`bbwp_owner`)."""
    df = _fixture_ohlcv(timeframe)
    service = IndicatorsService(df)
    service.calculate_oscillators()

    engine = service.df["bbwp"]
    owner = service.df["bbwp_owner"]
    tail = slice(-100, None)
    both_valid = engine.iloc[tail].notna() & owner.iloc[tail].notna()
    assert both_valid.any()
    gap = (engine.iloc[tail] - owner.iloc[tail]).abs()[both_valid]
    # Material divergence: on real 4h/1h BTC candles the two definitions
    # disagree by tens of percentile points somewhere in the last 100 bars.
    assert gap.max() > 10.0
