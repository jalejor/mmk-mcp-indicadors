"""AO parity vs the TradingView built-in (owner source, 2026-07-16).

The owner's chart runs the Pine v6 built-in:

    ao   = ta.sma(hl2, 5) - ta.sma(hl2, 34)
    diff = ao - ao[1]
    color = diff <= 0 ? RED : GREEN          # tie paints RED
    changeToGreen/Red = crossover/crossunder(diff, 0)

These tests pin: (1) the engine's `ta.ao` (pandas-ta-classic) is bit-equal
to the Pine formula, on synthetic and on real candles; (2) the new
`ao_diff` / `ao_color` / `ao_color_change` fields implement the exact Pine
colour semantics; (3) the documented divergence of the rules helpers
`ao_rising`/`ao_falling` on ties (strict comparisons: a flat AO bar is
NEITHER rising nor falling, while the Pine colour is RED).
"""

import json
import pathlib

import numpy as np
import pandas as pd

from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.setup_service import ao_falling, ao_rising

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _synthetic_ohlcv(n: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 0.6, size=n))
    high = close + rng.uniform(0.1, 1.0, size=n)
    low = close - rng.uniform(0.1, 1.0, size=n)
    open_ = close + rng.normal(0, 0.2, size=n)
    volume = 1000 + rng.uniform(-100, 200, size=n)
    index = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def _fixture_ohlcv(timeframe: str) -> pd.DataFrame:
    raw = json.loads((FIXTURES / f"btc_usdt_bitget_{timeframe}_20260713T1600.json").read_text())
    frame = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame.index = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame


def _pine_ao(high: pd.Series, low: pd.Series) -> pd.Series:
    hl2 = (high + low) / 2.0
    return hl2.rolling(5).mean() - hl2.rolling(34).mean()


# ---------------------------------------------------------------------------
# 1. Engine AO == Pine built-in formula
# ---------------------------------------------------------------------------

def test_engine_ao_equals_pine_formula_synthetic():
    df = _synthetic_ohlcv()
    service = IndicatorsService(df)
    service.calculate_all()
    expected = _pine_ao(df["high"], df["low"])
    pd.testing.assert_series_equal(
        service.df["ao"], expected, check_names=False, rtol=0, atol=1e-9
    )
    # Warmup exactly like Pine: na for the first 33 bars, valid from bar 34.
    assert service.df["ao"].iloc[:33].isna().all()
    assert service.df["ao"].iloc[33:].notna().all()


def test_engine_ao_equals_pine_formula_real_candles():
    df = _fixture_ohlcv("4h")
    service = IndicatorsService(df)
    service.calculate_oscillators()
    expected = _pine_ao(df["high"], df["low"])
    assert np.allclose(
        service.df["ao"].iloc[33:], expected.iloc[33:], rtol=0, atol=1e-9
    )


# ---------------------------------------------------------------------------
# 2. Colour semantics: sign of diff, tie = RED, change = cross of diff with 0
# ---------------------------------------------------------------------------

def test_ao_color_is_sign_of_diff_with_tie_red():
    df = _synthetic_ohlcv()
    service = IndicatorsService(df)
    result = service.calculate_oscillators()

    diff = service.df["ao"].diff()
    for i in range(len(df)):
        d = diff.iloc[i]
        color = service.df["ao_color"].iloc[i]
        if pd.isna(d):
            assert color is None
        elif d > 0:
            assert color == "green"
        else:  # d <= 0 — ties paint RED, like the Pine `diff <= 0 ? red : green`
            assert color == "red"
    assert result["ao_color"] in ("green", "red")
    assert result["ao_diff"] == float(diff.dropna().iloc[-1])


def test_ao_flat_bar_paints_red():
    """A candle where AO repeats exactly (diff == 0) must read RED."""
    n = 60
    index = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    base = pd.DataFrame(
        {
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
            "volume": 1000.0,
        },
        index=index,
    )
    service = IndicatorsService(base)
    service.calculate_oscillators()
    # Constant hl2 -> AO = 0 for every valid bar -> diff = 0 -> red.
    valid_colors = service.df["ao_color"].dropna()
    assert (valid_colors == "red").all()


def test_ao_color_change_events():
    """to_green iff diff crosses over 0; to_red iff it crosses under."""
    def result_for(diff_path):
        # `_ao_color_change` consumes the diff series directly.
        return IndicatorsService._ao_color_change(pd.Series(diff_path, dtype="float64"))

    assert result_for([-0.5, -0.2, 0.3]) == "to_green"      # diff crosses over 0
    assert result_for([0.4, 0.1, -0.2]) == "to_red"
    assert result_for([0.2, 0.0, 0.5]) == "to_green"        # from tie (<= 0) to positive
    assert result_for([0.2, 0.5, 0.7]) is None              # stayed green
    assert result_for([-0.2, -0.5, -0.7]) is None           # stayed red
    assert result_for([0.5]) is None                        # not enough history


# ---------------------------------------------------------------------------
# 3. Documented divergence: rules helpers vs the Pine colour on ties
# ---------------------------------------------------------------------------

def test_rules_tie_semantics_diverge_from_pine_color_documented():
    """`ao_rising`/`ao_falling` use STRICT comparisons: a flat AO bar is
    neither rising nor falling for the rules, while the owner's chart paints
    it RED. Documented on purpose (AO parity check, 2026-07-16) — the rules
    keep their historical semantics; Pine-exact reads must use `ao_color`.
    """
    flat = pd.Series([1.0, 1.0])
    assert ao_rising(flat) is False
    assert ao_falling(flat) is False  # Pine colour here would be RED


def test_zero_cross_reads_use_ao_sign_not_color():
    """The E-element zero-cross reads (`zero_cross_age`) act on the SIGN of
    AO itself (above/below zero), which matches the owner's 'AO crosses 0'
    reading — the colour is a *different* signal (momentum of AO)."""
    from controllers.metrics.setup_service import zero_cross_age

    ao = pd.Series([-1.0, -0.5, 0.4, 0.8])
    assert zero_cross_age(ao, direction="up", confirm_bars=1) == 1
