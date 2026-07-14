"""Tests for the in-memory TTL cache on MarketDataService."""

from typing import Any, List

import pandas as pd
import pytest

from controllers.metrics.market_data_service import MarketDataService


class _FakeExchange:
    """Stand-in for ccxt that records every fetch_ohlcv call."""

    def __init__(self, payload: List[List[Any]]):
        self.payload = payload
        self.calls: int = 0

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500):
        self.calls += 1
        return list(self.payload)


@pytest.fixture(autouse=True)
def _reset_cache():
    MarketDataService.clear_cache()
    yield
    MarketDataService.clear_cache()


def test_cache_returns_same_data_without_extra_fetch():
    svc = MarketDataService(exchange_name="binance")
    fake = _FakeExchange([[1, 1, 1, 1, 1, 1] for _ in range(5)])
    svc.exchange = fake  # swap the real ccxt client out

    first = svc.get_ohlcv("BTC/USDT", "1h", 5)
    second = svc.get_ohlcv("BTC/USDT", "1h", 5)
    assert fake.calls == 1
    assert isinstance(first, pd.DataFrame)
    pd.testing.assert_frame_equal(first, second)


def test_cache_returns_defensive_copy():
    # Use distinct timestamps so the index is unique (the rows the fake
    # exchange returns in the other tests share the same timestamp on
    # purpose to make those assertions readable).
    svc = MarketDataService(exchange_name="binance")
    fake = _FakeExchange(
        [[i * 60_000, 1, 1, 1, 1, 1] for i in range(3)]
    )
    svc.exchange = fake

    first = svc.get_ohlcv("BTC/USDT", "1h", 3)
    first.iat[0, first.columns.get_loc("close")] = 999  # mutate returned DF
    second = svc.get_ohlcv("BTC/USDT", "1h", 3)
    assert second.iat[0, second.columns.get_loc("close")] != 999


def test_cache_disabled_when_use_cache_false():
    svc = MarketDataService(exchange_name="binance")
    fake = _FakeExchange([[1, 1, 1, 1, 1, 1] for _ in range(2)])
    svc.exchange = fake

    svc.get_ohlcv("BTC/USDT", "1h", 2, use_cache=False)
    svc.get_ohlcv("BTC/USDT", "1h", 2, use_cache=False)
    assert fake.calls == 2


def test_cache_keyed_by_symbol_timeframe_and_limit():
    svc = MarketDataService(exchange_name="binance")
    fake = _FakeExchange([[1, 1, 1, 1, 1, 1] for _ in range(2)])
    svc.exchange = fake

    svc.get_ohlcv("BTC/USDT", "1h", 2)
    svc.get_ohlcv("ETH/USDT", "1h", 2)
    svc.get_ohlcv("BTC/USDT", "5m", 2)
    svc.get_ohlcv("BTC/USDT", "1h", 3)
    assert fake.calls == 4


def test_stale_candle_not_reused_after_close_despite_long_ttl(monkeypatch):
    """P0 (2026-07-13): the shared cache took the TTL of the FIRST request, so a
    1d/1w first request kept 30m data alive for hours — the M1 monitor read the
    same stale 30m candle for ~11h. The entry must self-invalidate the instant
    the 30m candle closes, *regardless* of any long TTL a prior request set.
    """
    from controllers.metrics import market_data_service as mds

    # t0 sits 1200s into a 30m (1800s) candle, i.e. 600s before its close.
    clock = {"t": 900_000 * 1800 + 1200.0}
    monkeypatch.setattr(mds, "_now", lambda: clock["t"])

    svc = MarketDataService(exchange_name="binance")
    fake = _FakeExchange([[i * 60_000, 1, 1, 1, 1, 1] for i in range(50)])
    svc.exchange = fake

    # First-ever request is 1d: in the old shared-cache code this pinned the
    # cache TTL at half a day, and every later timeframe inherited it.
    svc.get_ohlcv("BTC/USDT", "1d", 5)
    calls_after_1d = fake.calls

    # 30m request: fetched once, then a same-candle repeat is a cache hit.
    svc.get_ohlcv("BTC/USDT", "30m", 5)
    svc.get_ohlcv("BTC/USDT", "30m", 5)
    assert fake.calls == calls_after_1d + 1  # only one 30m fetch so far

    # Advance 700s: past the NEXT 30m close (t0 + 600s) but far inside the long
    # TTL the 1d request would have imposed. The candle bucket changed, so the
    # entry must be considered stale and re-fetched — not served from cache.
    clock["t"] += 700
    svc.get_ohlcv("BTC/USDT", "30m", 5)
    assert fake.calls == calls_after_1d + 2  # re-fetched: stale entry NOT reused

    # And within the same (new) candle it caches again.
    svc.get_ohlcv("BTC/USDT", "30m", 5)
    assert fake.calls == calls_after_1d + 2


def test_expected_last_closed_candle_ts_steps_at_candle_close():
    from controllers.metrics.market_data_service import expected_last_closed_candle_ts

    # 30m candle: within one candle the value is constant; across a close it steps.
    base = 900_000 * 1800  # aligned to a 30m boundary (seconds)
    inside = expected_last_closed_candle_ts("30m", base + 100.0)
    later_same = expected_last_closed_candle_ts("30m", base + 1799.0)
    after_close = expected_last_closed_candle_ts("30m", base + 1801.0)
    assert inside == later_same
    assert after_close == inside + 1800 * 1000  # advanced exactly one candle
    # Unknown timeframes have no alignment to bind to.
    assert expected_last_closed_candle_ts("??", base) is None
