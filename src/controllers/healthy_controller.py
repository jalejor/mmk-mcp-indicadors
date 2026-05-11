"""Health endpoints.

`/liveness` is a simple "the process is up" probe used by the orchestrator.
`/healthy` is a richer readiness probe that also checks the upstream
exchange (Binance by default).  When the exchange call fails or times out
the endpoint downgrades to `degraded` so the load balancer can route
traffic away while the process keeps responding.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from os import getenv
from typing import Any, Dict

import ccxt

_PROCESS_START_TS = time.time()
_VERSION = getenv("APP_VERSION", "1.0.0")
_APP_ID = getenv("APP_ID", "mmk-mcp-indicadors")
_ENVIRONMENT = getenv("PY_ENV", "development")

_EXCHANGE_PROBE_TIMEOUT_S = float(getenv("HEALTH_EXCHANGE_TIMEOUT", "3"))


class HealthyController:
    """Backwards-compatible shim around the module-level helpers."""

    def __init__(self, app_id: str = _APP_ID, environment: str = _ENVIRONMENT):
        self._app_status = {"message": f"{app_id} OK", "environment": environment}

    def root(self) -> Dict[str, Any]:
        return self._app_status

    def healthy(self) -> Dict[str, Any]:
        return healthy()

    def liveness(self) -> Dict[str, Any]:
        return liveness()


def liveness() -> Dict[str, Any]:
    """Return immediately — the process is alive."""
    return {
        "status": "alive",
        "environment": _ENVIRONMENT,
        "uptime_seconds": int(time.time() - _PROCESS_START_TS),
        "version": _VERSION,
    }


def root() -> Dict[str, Any]:
    return {"message": f"{_APP_ID} OK", "environment": _ENVIRONMENT}


def _probe_binance() -> str:
    try:
        client = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(client.fetch_ticker, "BTC/USDT")
            future.result(timeout=_EXCHANGE_PROBE_TIMEOUT_S)
        return "ok"
    except FutureTimeoutError:
        return "error: timeout"
    except Exception as exc:  # pragma: no cover - depends on network
        return f"error: {exc}"


def healthy() -> Dict[str, Any]:
    binance_status = _probe_binance()
    overall = "healthy" if binance_status == "ok" else "degraded"
    return {
        "status": overall,
        "exchange_binance": binance_status,
        "uptime_seconds": int(time.time() - _PROCESS_START_TS),
        "version": _VERSION,
        "environment": _ENVIRONMENT,
    }
