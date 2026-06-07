import math

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.indicators_service import IndicatorsService


def _dummy_df(n: int = 30, seed: int = 0):
    """Generate a synthetic OHLCV DataFrame with mild random walk volatility."""
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = base + rng.uniform(0.1, 1.0, size=n)
    low = base - rng.uniform(0.1, 1.0, size=n)
    open_ = base + rng.normal(0, 0.2, size=n)
    close = base + rng.normal(0, 0.2, size=n)
    volume = 1000 + rng.uniform(-100, 200, size=n)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="h"),
            "open": open_,
            "high": np.maximum.reduce([open_, close, high]),
            "low": np.minimum.reduce([open_, close, low]),
            "close": close,
            "volume": volume,
        }
    )
    df.set_index("timestamp", inplace=True)
    return df


def test_indicators_calculation_not_empty():
    df = _dummy_df()
    service = IndicatorsService(df)
    indicators = service.calculate_all()

    expected_keys = [
        "rsi14",
        "adx14",
        "plus_di",
        "minus_di",
        "bbw",
        "bbwp",
        "bbwp_ma4",
        "ao",
        "sma50",
        "ema50",
        "sma200",
        "ema200",
        "konkorde_azul",
        "konkorde_verde",
        "konkorde_marron",
        "konkorde_value",
        "konkorde_signal",
        "atr",
        "volatility_20",
    ]

    for key in expected_keys:
        assert key in indicators, f"Falta indicador {key}"
        assert indicators[key] is not None, f"Indicador {key} es None"


def test_konkorde_returns_all_lines():
    df = _dummy_df(n=300)
    indicators = IndicatorsService(df).calculate_all()
    for key in ("konkorde_azul", "konkorde_verde", "konkorde_marron", "konkorde_signal"):
        assert key in indicators
    # `konkorde_value` keeps backwards compatibility as alias of marron.
    assert indicators["konkorde_value"] == pytest.approx(indicators["konkorde_marron"], nan_ok=True)


def test_konkorde_signal_classification():
    assert IndicatorsService._classify_konkorde(azul=10.0, verde=20.0, marron=15.0) == "bullish_strong"
    assert IndicatorsService._classify_konkorde(azul=10.0, verde=2.0, marron=5.0) == "bullish_weak"
    assert IndicatorsService._classify_konkorde(azul=-5.0, verde=-20.0, marron=-10.0) == "bearish_strong"
    assert IndicatorsService._classify_konkorde(azul=-15.0, verde=-2.0, marron=-5.0) == "bearish_weak"
    assert IndicatorsService._classify_konkorde(azul=0.0, verde=0.0, marron=0.0) == "neutral"


def test_bbwp_in_range_0_100():
    df = _dummy_df(n=400, seed=42)
    indicators = IndicatorsService(df).calculate_all()
    bbwp = indicators["bbwp"]
    assert not math.isnan(bbwp)
    assert 0.0 <= bbwp <= 100.0


def test_bbwp_extreme_compression():
    """When the most recent bars sit at the lowest BBW seen in the lookback,
    BBWP should land in the very low range."""
    n = 350
    rng = np.random.default_rng(7)
    # First 80% noisy; final 20% completely flat -> BBW collapses to ~0.
    cut = int(n * 0.8)
    noisy = 100.0 + np.cumsum(rng.normal(0, 1.5, size=cut))
    flat = np.full(n - cut, noisy[-1])
    base = np.concatenate([noisy, flat])
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="h"),
            "open": base,
            "high": base + 1e-6,
            "low": base - 1e-6,
            "close": base,
            "volume": np.full(n, 1000.0),
        }
    )
    df.set_index("timestamp", inplace=True)
    indicators = IndicatorsService(df).calculate_all()
    # In the most extreme compression we have seen the percentile rank should
    # be at the very bottom of the historical distribution.
    assert indicators["bbwp"] <= 25.0


def test_adx_exposes_di():
    df = _dummy_df(n=200, seed=11)
    indicators = IndicatorsService(df).calculate_all()
    assert isinstance(indicators["plus_di"], float)
    assert isinstance(indicators["minus_di"], float)
    assert isinstance(indicators["adx14"], float)
