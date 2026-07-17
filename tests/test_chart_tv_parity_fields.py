"""/v1/charts + /v1/metrics expose the TradingView-parity fields (additive).

Same offline pattern as `test_chart_konkorde_and_span.py`: the market-data
loader is monkeypatched with a seeded synthetic OHLCV frame. Pins that the
new fields exist, align 1:1 with the candles, serialise NaN as null, and
that the legacy fields are untouched (nothing here rewires rules).
"""

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.chart_service import ChartService
from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.market_data_service import MarketDataService


def _synthetic_ohlcv(periods: int = 400) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    end = pd.Timestamp.utcnow().floor("h")
    index = pd.date_range(end=end, periods=periods, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(0, 0.5, periods))
    high = close + rng.uniform(0.1, 0.6, periods)
    low = close - rng.uniform(0.1, 0.6, periods)
    open_ = close + rng.normal(0, 0.2, periods)
    volume = rng.uniform(500, 1500, periods)
    return pd.DataFrame(
        {
            "timestamp": (index.asi8 // 10**6),
            "open": open_, "high": high, "low": low, "close": close,
            "volume": volume,
        },
        index=index,
    )


@pytest.fixture
def chart_result(monkeypatch):
    df = _synthetic_ohlcv()

    monkeypatch.setattr(
        MarketDataService,
        "get_ohlcv",
        lambda self, symbol, timeframe="1h", limit=500, use_cache=True, drop_forming=True: df.copy(),
    )
    service = ChartService(symbol="BTC/USDT", span="7d", preferred_timeframe="1h")
    return service.execute()


def test_chart_payload_has_tv_parity_fields(chart_result):
    for key in ("ao_diff", "ao_color", "bbwp_owner", "trend_speed"):
        assert key in chart_result, key


def test_tv_parity_series_align_with_candles(chart_result):
    n = chart_result["total_candles"]
    assert len(chart_result["ao_diff"]) == n
    assert len(chart_result["ao_color"]) == n
    assert len(chart_result["bbwp_owner"]["bbwp"]) == n
    assert len(chart_result["bbwp_owner"]["ma5"]) == n
    assert len(chart_result["trend_speed"]["dyn_ema"]) == n
    assert len(chart_result["trend_speed"]["speed"]) == n
    assert len(chart_result["trend_speed"]["trendspeed"]) == n


def test_tv_parity_values_json_safe(chart_result):
    for value in chart_result["ao_diff"]:
        assert value is None or isinstance(value, float)
    assert set(v for v in chart_result["ao_color"] if v is not None) <= {"green", "red"}
    for value in chart_result["bbwp_owner"]["bbwp"]:
        assert value is None or (isinstance(value, float) and 0.0 <= value <= 100.0)
    stats = chart_result["trend_speed"]["stats"]
    assert isinstance(stats, dict)
    for key, value in stats.items():
        assert value is None or isinstance(value, (int, float)), key


def test_legacy_oscillator_fields_untouched(chart_result):
    """The pre-existing panels keep their exact shape (dashboard contract)."""
    n = chart_result["total_candles"]
    assert len(chart_result["ao"]) == n
    assert len(chart_result["bbwp"]) == n
    assert set(chart_result["adx"].keys()) == {"adx", "plus_di", "minus_di"}


def test_metrics_result_has_tv_parity_keys():
    df = _synthetic_ohlcv(400)
    result = IndicatorsService(df).calculate_all()
    for key in (
        "bbwp_owner", "bbwp_owner_ma5",
        "ao_diff", "ao_color", "ao_color_change",
        "trend_speed", "trend_speed_raw", "trend_speed_dyn_ema", "trend_speed_stats",
    ):
        assert key in result, key
    assert isinstance(result["trend_speed_stats"], dict)


def test_span_shorter_than_warmup_still_works(monkeypatch):
    """A short window (fewer candles than the TSA/BBWP warmup) must not
    crash — parity fields simply come back as nulls."""
    df = _synthetic_ohlcv(60)

    monkeypatch.setattr(
        MarketDataService,
        "get_ohlcv",
        lambda self, symbol, timeframe="1h", limit=500, use_cache=True, drop_forming=True: df.copy(),
    )
    service = ChartService(symbol="BTC/USDT", span="2d", preferred_timeframe="1h")
    result = service.execute()
    assert len(result["trend_speed"]["speed"]) == result["total_candles"]
    assert all(v is None for v in result["trend_speed"]["trendspeed"])
