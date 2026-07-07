"""Tests for the Konkorde series in /v1/charts and the 1M span fix.

No network: `MarketDataService.get_ohlcv` is monkeypatched with a seeded
synthetic OHLCV frame.
"""

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.chart_service import ChartService
from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.market_data_service import MarketDataService


# ---------------------------------------------------------------------------
# Konkorde series in the charts payload
# ---------------------------------------------------------------------------

def _synthetic_ohlcv(periods: int = 400) -> pd.DataFrame:
    """Seeded random-walk OHLCV ending now (UTC), hourly candles."""
    rng = np.random.RandomState(42)
    end = pd.Timestamp.utcnow().floor("h")
    index = pd.date_range(end=end, periods=periods, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(0, 0.5, periods))
    high = close + rng.uniform(0.1, 0.6, periods)
    low = close - rng.uniform(0.1, 0.6, periods)
    open_ = close + rng.normal(0, 0.2, periods)
    volume = rng.uniform(500, 1500, periods)
    df = pd.DataFrame(
        {
            "timestamp": (index.asi8 // 10**6),
            "open": open_, "high": high, "low": low, "close": close,
            "volume": volume,
        },
        index=index,
    )
    return df


@pytest.fixture
def chart_result(monkeypatch):
    frame = _synthetic_ohlcv()
    monkeypatch.setattr(
        MarketDataService,
        "get_ohlcv",
        lambda self, symbol, timeframe="1h", limit=500, use_cache=True, drop_forming=True: frame.copy(),
    )
    service = ChartService(symbol="BTC/USDT", span="7d", preferred_timeframe="1h")
    return service.execute(), frame


def test_charts_response_includes_konkorde_series(chart_result):
    result, _frame = chart_result
    assert "konkorde" in result
    assert set(result["konkorde"].keys()) == {"marron", "verde", "azul"}


def test_konkorde_series_align_one_to_one_with_candles(chart_result):
    result, _frame = chart_result
    n = len(result["chart_data"])
    assert n == result["total_candles"]
    for line in ("marron", "verde", "azul"):
        values = result["konkorde"][line]
        assert len(values) == n
        assert all(v is None or isinstance(v, float) for v in values)
    # With a 7d window of hourly candles the tail must be numeric.
    assert result["konkorde"]["marron"][-1] is not None
    assert result["konkorde"]["verde"][-1] is not None
    assert result["konkorde"]["azul"][-1] is not None


def test_konkorde_values_match_indicators_service_on_same_window(chart_result):
    """The series must come from the SAME window the chart returns."""
    result, frame = chart_result
    start = pd.Timestamp(result["start"])
    end = pd.Timestamp(result["end"])
    window = frame.loc[start:end]

    service = IndicatorsService(window)
    service.calculate_konkorde()
    expected_last = float(service.df["konkorde_marron"].iloc[-1])
    assert result["konkorde"]["marron"][-1] == pytest.approx(expected_last)


def test_charts_existing_contract_unchanged(chart_result):
    """Backward-compat: every pre-existing key keeps its place and shape."""
    result, _frame = chart_result
    for key in (
        "symbol", "exchange", "timeframe", "start", "end", "duration_hours",
        "total_candles", "chart_data", "metrics", "optimization",
    ):
        assert key in result
    point = result["chart_data"][0]
    assert set(point.keys()) == {
        "timestamp", "datetime", "open", "high", "low", "close", "volume",
    }
