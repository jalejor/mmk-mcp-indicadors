"""Closed-candle-only live path (spec §0.1).

ccxt returns the in-progress candle as the last row; `get_ohlcv` must drop it
by default so live evaluations never repaint. Chart rendering opts out with
`drop_forming=False`.
"""

import time
from typing import Any, List

import pytest

from controllers.metrics.market_data_service import MarketDataService


class _FakeExchange:
    def __init__(self, payload: List[List[Any]]):
        self.payload = payload
        self.calls = 0

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500):
        self.calls += 1
        return list(self.payload)


@pytest.fixture(autouse=True)
def _reset_cache():
    MarketDataService.clear_cache()
    yield
    MarketDataService.clear_cache()


def _payload_with_forming_last(timeframe_s: int, n: int = 5) -> List[List[Any]]:
    """n candles where the last one opened less than one timeframe ago."""
    now_ms = int(time.time() * 1000)
    duration_ms = timeframe_s * 1000
    forming_open = now_ms - duration_ms // 2  # opened half a candle ago
    rows = []
    for i in range(n - 1, 0, -1):
        rows.append([forming_open - i * duration_ms, 1, 1, 1, 1, 1])
    rows.append([forming_open, 1, 1, 1, 1, 1])
    return rows


def test_forming_candle_dropped_by_default():
    svc = MarketDataService(exchange_name="bitget")
    svc.exchange = _FakeExchange(_payload_with_forming_last(3600, n=5))
    df = svc.get_ohlcv("BTC/USDT", "1h", 5)
    assert len(df) == 4  # forming last row discarded


def test_forming_candle_kept_on_opt_out():
    svc = MarketDataService(exchange_name="bitget")
    svc.exchange = _FakeExchange(_payload_with_forming_last(3600, n=5))
    df = svc.get_ohlcv("BTC/USDT", "1h", 5, drop_forming=False)
    assert len(df) == 5


def test_closed_last_candle_not_dropped():
    svc = MarketDataService(exchange_name="bitget")
    now_ms = int(time.time() * 1000)
    duration_ms = 3600 * 1000
    # Last candle opened two full timeframes ago -> closed.
    payload = [[now_ms - i * duration_ms, 1, 1, 1, 1, 1] for i in range(6, 1, -1)]
    svc.exchange = _FakeExchange(payload)
    df = svc.get_ohlcv("BTC/USDT", "1h", 5)
    assert len(df) == 5


def test_cache_serves_both_modes():
    """The cache stores the raw payload; the filter is applied per call."""
    svc = MarketDataService(exchange_name="bitget")
    fake = _FakeExchange(_payload_with_forming_last(3600, n=5))
    svc.exchange = fake
    dropped = svc.get_ohlcv("BTC/USDT", "1h", 5)
    full = svc.get_ohlcv("BTC/USDT", "1h", 5, drop_forming=False)
    assert fake.calls == 1  # second call was a cache hit
    assert len(dropped) == 4
    assert len(full) == 5


def _month_open_ms(year: int, month: int) -> int:
    from datetime import datetime, timezone

    return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)


def test_forming_monthly_candle_dropped(monkeypatch):
    """Regression (audit 2026-11-01): `1M` has no fixed duration, so it was
    not in `_TIMEFRAME_TO_SECONDS` and the forming month was never dropped —
    the only timeframe where the "closed candles only" path repainted."""
    from controllers.metrics import market_data_service as mds

    # Frozen "now": 2026-11-01 05:00 UTC -> the November candle is forming.
    monkeypatch.setattr(mds, "_now", lambda: _month_open_ms(2026, 11) / 1000.0 + 5 * 3600)
    payload = [[_month_open_ms(2026, m), 1, 1, 1, 1, 1] for m in (7, 8, 9, 10, 11)]
    svc = MarketDataService(exchange_name="bitget")
    svc.exchange = _FakeExchange(payload)
    dropped = svc.get_ohlcv("BTC/USDT", "1M", 5)
    assert len(dropped) == 4
    assert int(dropped["timestamp"].iloc[-1]) == _month_open_ms(2026, 10)
    full = svc.get_ohlcv("BTC/USDT", "1M", 5, drop_forming=False)
    assert len(full) == 5


def test_closed_monthly_candle_kept_across_year_boundary(monkeypatch):
    from controllers.metrics import market_data_service as mds

    # Frozen "now": 2027-01-01 00:00 UTC exactly -> December 2026 just closed.
    monkeypatch.setattr(mds, "_now", lambda: _month_open_ms(2027, 1) / 1000.0)
    payload = [[_month_open_ms(2026, m), 1, 1, 1, 1, 1] for m in (9, 10, 11, 12)]
    svc = MarketDataService(exchange_name="bitget")
    svc.exchange = _FakeExchange(payload)
    assert len(svc.get_ohlcv("BTC/USDT", "1M", 4)) == 4


def test_unknown_timeframe_left_untouched():
    svc = MarketDataService(exchange_name="bitget")
    svc.exchange = _FakeExchange([[1, 1, 1, 1, 1, 1] for _ in range(3)])
    df = svc.get_ohlcv("BTC/USDT", "??", 3)
    assert len(df) == 3
