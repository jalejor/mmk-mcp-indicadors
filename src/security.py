"""API key authentication and rate limiting wiring.

API keys are read from the `API_KEYS` environment variable (comma-separated)
at startup.  When the variable is empty or unset, auth is disabled — useful
for local development.

Rate limiting is provided by `slowapi` and is registered on the FastAPI
application.  Per-route overrides can use the `@limiter.limit("5/minute")`
decorator from this module.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address
    from starlette.responses import JSONResponse
    _SLOWAPI_AVAILABLE = True
except Exception:  # pragma: no cover
    _SLOWAPI_AVAILABLE = False
    Limiter = None  # type: ignore[assignment]


_LOGGER = logging.getLogger(__name__)

# Default rate limit applied to every endpoint unless overridden.
DEFAULT_RATE_LIMIT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
BACKTEST_RATE_LIMIT = os.getenv("RATE_LIMIT_BACKTEST", "5/minute")


def _load_api_keys() -> List[str]:
    raw = os.getenv("API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def api_key_dependency(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency that validates the incoming `X-API-Key` header.

    If `API_KEYS` is empty the check is skipped (development mode).  The
    `Request` is taken to allow future per-key rate-limit accounting.
    """
    keys = _load_api_keys()
    if not keys:
        return  # auth disabled
    if x_api_key is None or x_api_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


limiter: Optional["Limiter"] = None
if _SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE_LIMIT])


def install_security(app: FastAPI) -> None:
    """Wire rate limiting + global request log into the FastAPI app."""
    if not _SLOWAPI_AVAILABLE or limiter is None:
        _LOGGER.warning("slowapi not installed; rate limiting disabled")
        return
    app.state.limiter = limiter

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "rate limit exceeded", "detail": str(exc.detail)},
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)


__all__ = [
    "api_key_dependency",
    "install_security",
    "limiter",
    "DEFAULT_RATE_LIMIT",
    "BACKTEST_RATE_LIMIT",
]
