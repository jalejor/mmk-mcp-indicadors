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
