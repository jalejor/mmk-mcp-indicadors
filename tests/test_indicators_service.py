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
        "konkorde_media",
        "konkorde_value",
        "konkorde_signal",
        "bbwp_ma5",
        "bbwp_legacy",
        "bbw13",
        "atr",
        "volatility_20",
    ]

    for key in expected_keys:
        assert key in indicators, f"Falta indicador {key}"
        assert indicators[key] is not None, f"Indicador {key} es None"


def test_konkorde_returns_all_lines():
    df = _dummy_df(n=300)
    indicators = IndicatorsService(df).calculate_all()
    for key in ("konkorde_azul", "konkorde_verde", "konkorde_marron", "konkorde_media", "konkorde_signal"):
        assert key in indicators
    # `konkorde_value` keeps backwards compatibility as alias of marron.
    assert indicators["konkorde_value"] == pytest.approx(indicators["konkorde_marron"], nan_ok=True)


def test_konkorde_signal_classification():
    """Blai5 reading: trend = marron vs media, strength = strong hands (azul)."""
    classify = IndicatorsService._classify_konkorde
    assert classify(azul=10.0, verde=70.0, marron=60.0, media=50.0) == "bullish_strong"
    assert classify(azul=-3.0, verde=70.0, marron=60.0, media=50.0) == "bullish_weak"
    assert classify(azul=-5.0, verde=20.0, marron=30.0, media=45.0) == "bearish_strong"
    assert classify(azul=4.0, verde=20.0, marron=30.0, media=45.0) == "bearish_weak"
    assert classify(azul=0.0, verde=50.0, marron=50.0, media=50.0) == "neutral"
    # A positive brown line alone is not bullish on the real indicator.
    assert classify(azul=-1.0, verde=40.0, marron=55.0, media=60.0) == "bearish_strong"


def test_bbwp_default_is_the_owner_tv_definition():
    """`bbwp` == The_Caretaker port with the owner's settings (13/256/5)."""
    df = _dummy_df(n=400, seed=42)
    service = IndicatorsService(df)
    indicators = service.calculate_all()
    assert indicators["bbwp_definition"] == "tv"
    assert indicators["bbwp"] == pytest.approx(indicators["bbwp_tv"])
    assert indicators["bbwp"] == pytest.approx(indicators["bbwp_owner"])
    assert indicators["bbwp_ma5"] == pytest.approx(indicators["bbwp_owner_ma5"])
    pd.testing.assert_series_equal(service.df["bbwp"], service.df["bbwp_owner"], check_names=False)
    # The old definition stays reachable for comparisons with recorded history.
    assert service.df["bbwp_legacy"].notna().any()
    assert indicators["bbwp_legacy"] != pytest.approx(indicators["bbwp"])


def test_bbwp_legacy_definition_selectable_for_rule_packs():
    """The versioned rule packs opt into the pre-2026-11-01 series."""
    df = _dummy_df(n=400, seed=42)
    service = IndicatorsService(df, bbwp_definition="legacy")
    indicators = service.calculate_all()
    assert indicators["bbwp_definition"] == "legacy"
    assert indicators["bbwp"] == pytest.approx(indicators["bbwp_legacy"])
    pd.testing.assert_series_equal(service.df["bbwp"], service.df["bbwp_legacy"], check_names=False)
    # The TV series is still exposed alongside (aliases included).
    pd.testing.assert_series_equal(service.df["bbwp_tv"], service.df["bbwp_owner"], check_names=False)
    with pytest.raises(ValueError):
        IndicatorsService(df, bbwp_definition="nope")


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
