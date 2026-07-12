"""Fresh ticker (last/bid/ask) via ccxt `fetch_ticker` — BYPASSES the OHLCV cache.

The OHLCV `TTLCache` TTL is half a timeframe (up to 30 min on 1h bars), which
made the "current price" derived from `charts` stale by up to 30 minutes. This
service calls `fetch_ticker` directly (a separate ccxt endpoint) behind its own
tiny TTL (<=10s) so bursts don't hit exchange rate limits. Handles perp symbols
(`:USDT`) exactly like the OHLCV path (same exchange client config).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from .market_data_service import DEFAULT_EXCHANGE, MarketDataService

_TTL_SECONDS = 5.0
_CACHE: Dict[Any, Any] = {}
_CLIENTS: Dict[str, Any] = {}
_LOCK = threading.Lock()


def _shared_exchange(name: str):
    if name not in _CLIENTS:
        if name not in MarketDataService.SUPPORTED_EXCHANGES:
            raise ValueError(f"Exchange no soportado: {name}")
        _CLIENTS[name] = MarketDataService.SUPPORTED_EXCHANGES[name]({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
    return _CLIENTS[name]


def _num(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) else None


class TickerService:
    def __init__(self, *, exchange: str = DEFAULT_EXCHANGE, client: Any = None):
        self.exchange_name = exchange.lower()
        self._client = client

    def _exchange(self):
        return self._client if self._client is not None else _shared_exchange(self.exchange_name)

    def fetch(self, symbol: str) -> Dict[str, Any]:
        key = (self.exchange_name, symbol)
        now = time.time()
        with _LOCK:
            cached = _CACHE.get(key)
            if cached is not None and cached[0] > now:
                return cached[1]

        ticker = self._exchange().fetch_ticker(symbol)
        payload = {
            "symbol": symbol,
            "last": _num(ticker.get("last")),
            "bid": _num(ticker.get("bid")),
            "ask": _num(ticker.get("ask")),
            "timestamp": ticker.get("timestamp"),
        }
        with _LOCK:
            _CACHE[key] = (now + _TTL_SECONDS, payload)
        return payload

    @classmethod
    def clear_cache(cls) -> None:
        with _LOCK:
            _CACHE.clear()
