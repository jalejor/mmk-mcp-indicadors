"""TickerService: fresh fetch_ticker, tiny cache, perp symbols — ccxt mocked."""

from controllers.metrics.ticker_service import TickerService


class _FakeExchange:
    def __init__(self):
        self.calls = 0
        self.last = 74.22

    def fetch_ticker(self, symbol):
        self.calls += 1
        return {"symbol": symbol, "last": self.last, "bid": 74.20, "ask": 74.24,
                "timestamp": 1_700_000_000_000}


def setup_function(_):
    TickerService.clear_cache()


def test_fetch_returns_last_bid_ask():
    ex = _FakeExchange()
    svc = TickerService(exchange="bitget", client=ex)
    payload = svc.fetch("CL/USDT:USDT")   # perp symbol
    assert payload == {"symbol": "CL/USDT:USDT", "last": 74.22, "bid": 74.20,
                       "ask": 74.24, "timestamp": 1_700_000_000_000}
    assert ex.calls == 1


def test_small_cache_avoids_bursts():
    ex = _FakeExchange()
    svc = TickerService(exchange="bitget", client=ex)
    svc.fetch("BTC/USDT")
    svc.fetch("BTC/USDT")   # within the <=10s TTL -> served from cache
    assert ex.calls == 1


def test_non_numeric_fields_become_null():
    class _NoBook:
        def fetch_ticker(self, symbol):
            return {"last": 100.0, "bid": None, "ask": None, "timestamp": None}

    svc = TickerService(exchange="bitget", client=_NoBook())
    payload = svc.fetch("BTC/USDT")
    assert payload["last"] == 100.0
    assert payload["bid"] is None and payload["ask"] is None
