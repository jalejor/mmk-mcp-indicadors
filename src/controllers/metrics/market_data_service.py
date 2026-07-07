"""Market data fetcher with an in-memory TTL cache.

Public exchange OHLCV calls are inherently rate-limited and a single
request can take hundreds of milliseconds, so we keep the most recent N
candles in a `cachetools.TTLCache` keyed by `(exchange, symbol, timeframe,
limit)`.  The TTL is half of the timeframe duration: half a minute for 1m
bars, half an hour for 1h bars, etc.

A per-key `asyncio.Lock` would be ideal but ccxt is sync, so we settle for
a coarse-grained `threading.Lock` to keep the cache thread-safe.  Cache
misses still hit ccxt; cache hits return a defensive copy of the
DataFrame so callers cannot mutate the shared object.
"""

from __future__ import annotations

import threading
import time
from os import getenv
from typing import Any, Dict, List, Optional, Tuple

import ccxt
import pandas as pd

try:
    from cachetools import TTLCache
except Exception:  # pragma: no cover - cachetools is a hard runtime dep
    TTLCache = None  # type: ignore[assignment]


_TIMEFRAME_TO_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
    "6h": 6 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "1d": 24 * 60 * 60,
    "3d": 3 * 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}


class _CacheEntry:
    __slots__ = ("df", "lock")

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.lock = threading.Lock()


# Default exchange for every endpoint/service. Binance geo-blocks US IPs
# (HTTP 451), and every cloud deployment lives in a US region, so the safe
# code default is bitget — binance can still be selected explicitly via the
# DEFAULT_EXCHANGE env var or the per-request `exchange` query param.
DEFAULT_EXCHANGE = getenv("DEFAULT_EXCHANGE", "bitget").lower()


class MarketDataService:
    """OHLCV fetcher backed by a shared TTL cache."""

    SUPPORTED_EXCHANGES = {
        "binance": ccxt.binance,
        "bitget": ccxt.bitget,
    }

    # Class-level cache so all instances share data.  Capped at 256 keys to
    # avoid unbounded memory growth in long-running processes.
    _CACHE_MAXSIZE = 256
    _CACHE: Optional["TTLCache[Tuple[str, str, str, int], _CacheEntry]"] = None
    _CACHE_LOCK = threading.Lock()

    def __init__(self, exchange_name: str = DEFAULT_EXCHANGE) -> None:
        exchange_name = exchange_name.lower()
        if exchange_name not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"Exchange no soportado: {exchange_name}")
        self.exchange_name = exchange_name
        self.exchange = self.SUPPORTED_EXCHANGES[exchange_name]({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    @classmethod
    def _get_cache(cls, ttl_seconds: int) -> Optional[Any]:
        """Return the shared TTL cache, lazily instantiated.

        We use the *largest* TTL ever requested as the cache TTL: ccxt
        responses are immutable for the lifetime of the candle, so a longer
        TTL only delays eviction, never returns stale data — each entry is
        timestamp-bound by the candle it represents.
        """
        if TTLCache is None:
            return None
        with cls._CACHE_LOCK:
            if cls._CACHE is None:
                cls._CACHE = TTLCache(maxsize=cls._CACHE_MAXSIZE, ttl=max(ttl_seconds, 60))
            return cls._CACHE

    @classmethod
    def clear_cache(cls) -> None:
        """Drop every cached entry — useful in tests."""
        with cls._CACHE_LOCK:
            if cls._CACHE is not None:
                cls._CACHE.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
        use_cache: bool = True,
        drop_forming: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV from the exchange (or the cache) as a DataFrame.

        ccxt returns the in-progress (forming) candle as the last row. With
        ``drop_forming=True`` (the default) that row is discarded so every
        consumer evaluates **closed candles only** — the live path would
        otherwise repaint (spec: docs/STRATEGY_SETUPS_SPEC.md §0.1). Callers
        that explicitly need the forming candle (e.g. chart rendering) must
        opt out with ``drop_forming=False``.

        The cache always stores the raw exchange payload; the forming-candle
        filter is applied on the returned copy, so cached data can serve both
        modes.
        """
        key = (self.exchange_name, symbol, timeframe, int(limit))
        ttl = max(_TIMEFRAME_TO_SECONDS.get(timeframe, 3600) // 2, 60)
        cache = self._get_cache(ttl) if use_cache else None

        if cache is not None:
            entry = cache.get(key)
            if entry is not None:
                with entry.lock:
                    df = entry.df.copy()
                return self._drop_forming_candle(df, timeframe) if drop_forming else df

        raw_ohlcv: List[List[Any]] = self.exchange.fetch_ohlcv(
            symbol=symbol, timeframe=timeframe, limit=limit
        )
        df = pd.DataFrame(raw_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("datetime", inplace=True)

        if cache is not None:
            cache[key] = _CacheEntry(df)

        result = df.copy()
        return self._drop_forming_candle(result, timeframe) if drop_forming else result

    @staticmethod
    def _drop_forming_candle(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Drop the last row when its candle has not closed yet.

        A candle is closed iff ``open_time + timeframe_duration <= now_utc``.
        Only the last row can be forming (ccxt appends it), so a single
        check is enough. Unknown timeframes are returned untouched.
        """
        if df.empty:
            return df
        duration_s = _TIMEFRAME_TO_SECONDS.get(timeframe)
        if duration_s is None:
            return df
        last_open_ms = int(df["timestamp"].iloc[-1])
        close_ms = last_open_ms + duration_s * 1000
        now_ms = time.time() * 1000.0
        if close_ms > now_ms:
            return df.iloc[:-1]
        return df
