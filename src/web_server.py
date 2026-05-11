import json
import logging
import time
from logging import getLogger
from os import getenv
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run
from yaml import safe_load

_DEVELOPMENT_ENV = 'development'
_ASGI_ENV = getenv('ASGI_ENV', "prod")

# Path to the logging config (override via env).
_DEFAULT_LOG_CONF = (Path(__file__).parent / 'log_conf.yaml').as_posix()
_LOG_CONFIG_PATH = getenv('LOG_CONFIG_PATH', _DEFAULT_LOG_CONF)

_API_VERSION = getenv('APP_VERSION', '1.0.0')
_SVC = getenv("APP_ID", "mmk-mcp-indicadors")
_PREFIX_PATH = getenv("PREFIX_PATH", "/v1").split("#", 1)[0].strip()
if _PREFIX_PATH and not _PREFIX_PATH.startswith("/"):
    _PREFIX_PATH = f"/{_PREFIX_PATH}"

_HEALTHY_PATH = getenv("HEALTHY_PATH", "/healthy")
_LIVENESS_PATH = getenv("LIVENESS_PATH", "/liveness")

_LOG_FORMAT = getenv("LOG_FORMAT", "text").lower()
_REQUEST_LOGGER = getLogger("mmk.requests")


class _JSONFormatter(logging.Formatter):
    """Minimal JSON log formatter for ingestion by Loki / CloudWatch / Datadog."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in ("args", "msg", "levelname", "name", "exc_info"):
                continue
            if key.startswith("_"):
                continue
            if key in payload:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = repr(value)
        return json.dumps(payload, default=str)


class Unless:
    def filter(self, record) -> bool:
        _, _, path, _, _ = record.args
        return path not in [
            f"{_PREFIX_PATH}/",
            f"{_PREFIX_PATH}{_HEALTHY_PATH}",
            f"{_PREFIX_PATH}{_LIVENESS_PATH}",
            f"{_PREFIX_PATH}/docs",
            f"{_PREFIX_PATH}/openapi.json",
        ]


def _maybe_install_json_logging() -> None:
    if _LOG_FORMAT != "json":
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger()
    # Replace handlers so we don't double-emit lines.
    root.handlers = [handler]
    root.setLevel(logging.INFO)


async def _log_request_middleware(request: Request, call_next):
    """Emit one structured log entry per request (method, path, status, latency)."""
    start = time.perf_counter()
    response = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        # Never log the request body or headers — they may contain API keys.
        _REQUEST_LOGGER.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": round(elapsed_ms, 2),
            },
        )


def start_fastapi():
    from routes import routes
    from security import install_security

    _maybe_install_json_logging()

    if _ASGI_ENV == "local":
        _ROOT = ""
        _DOCS_URL = "/docs"
        _OPENAPI_URL = "/openapi.json"
    else:
        _ROOT = _PREFIX_PATH
        _DOCS_URL = f"{_PREFIX_PATH.rstrip('/')}/docs"
        _OPENAPI_URL = f"{_PREFIX_PATH.rstrip('/')}/openapi.json"

    app = FastAPI(
        title=f"{_SVC} API",
        docs_url=_DOCS_URL,
        version=_API_VERSION,
        root_path=_ROOT,
        openapi_url=_OPENAPI_URL,
    )

    _ALLOWED_ORIGINS = getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_security(app)
    app.middleware("http")(_log_request_middleware)
    app.include_router(routes)

    getLogger("uvicorn.access").addFilter(Unless())

    return app


def launch_asgi_server(app: FastAPI):
    def _parse_int(value: str, default: int) -> int:
        try:
            clean = value.split("#", 1)[0].strip()
            return int(clean)
        except (ValueError, TypeError):
            return default

    _PORT = _parse_int(getenv("PORT", "3000"), 3000)
    _HOST = getenv("HOST", "0.0.0.0").split("#", 1)[0].strip()

    if _ASGI_ENV != _DEVELOPMENT_ENV:
        with open(_LOG_CONFIG_PATH, 'r') as f:
            log_config = safe_load(f)

        run(app, host=_HOST, port=_PORT, log_config=log_config)
