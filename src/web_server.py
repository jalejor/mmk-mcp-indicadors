from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logging import getLogger
from os import getenv
from uvicorn import run
from yaml import safe_load

_DEVELOPMENT_ENV = 'development'
_ASGI_ENV = getenv('ASGI_ENV', "prod")
from pathlib import Path

# Ruta al archivo de configuración de logging, permite sobreescritura vía env
_DEFAULT_LOG_CONF = (Path(__file__).parent / 'log_conf.yaml').as_posix()
_LOG_CONFIG_PATH = getenv('LOG_CONFIG_PATH', _DEFAULT_LOG_CONF)

_API_VERSION = getenv('DD_VERSION', '1.0.0')
_SVC = getenv("DD_SERVICE", "fastapi")
_PREFIX_PATH = getenv("PREFIX_PATH", "/v1").split("#", 1)[0].strip()
# Asegura que comience con "/"
if _PREFIX_PATH and not _PREFIX_PATH.startswith("/"):
    _PREFIX_PATH = f"/{_PREFIX_PATH}"

_HEALTHY_PATH = getenv("HEALTHY_PATH", "/healthy")
_LIVENESS_PATH = getenv("LIVENESS_PATH", "/liveness")


class Unless():
    def filter(self, record) -> bool:
        _, _, path, _, _ = record.args
        return path not in [
            f"{_PREFIX_PATH}/",
            f"{_PREFIX_PATH}{_HEALTHY_PATH}",
            f"{_PREFIX_PATH}{_LIVENESS_PATH}",
            f"{_PREFIX_PATH}/docs",
            f"{_PREFIX_PATH}/openapi.json"
        ]


def start_fastapi():
    from routes import routes

    # En local (ASGI_ENV=local) no aplicamos root_path para evitar 404 en Swagger
    if _ASGI_ENV == "local":
        _ROOT = ""
        _DOCS_URL = "/docs"
        _OPENAPI_URL = "/openapi.json"
    else:
        _ROOT = _PREFIX_PATH
        # Garantiza que únicamente hay una barra entre los segmentos
        _DOCS_URL = f"{_PREFIX_PATH.rstrip('/')}/docs"
        _OPENAPI_URL = f"{_PREFIX_PATH.rstrip('/')}/openapi.json"

    app = FastAPI(
        title=f"{_SVC} API",
        docs_url=_DOCS_URL,
        version=_API_VERSION,
        root_path=_ROOT,
        openapi_url=_OPENAPI_URL,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins="*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes)

    getLogger("uvicorn.access").addFilter(Unless())

    return app


def launch_asgi_server(app: FastAPI):
    
    # Permite comentarios en la variable de entorno PORT, p.e. "9000  # Puerto"
    def _parse_int(value: str, default: int) -> int:
        try:
            clean = value.split("#", 1)[0].strip()
            return int(clean)
        except (ValueError, TypeError):
            return default

    _PORT = _parse_int(getenv("PORT", "3000"), 3000)

    _HOST = getenv("HOST", "0.0.0.0").split("#", 1)[0].strip()

    if (_ASGI_ENV != _DEVELOPMENT_ENV):

        with open(_LOG_CONFIG_PATH, 'r') as f:
            log_config = safe_load(f)

        run(app, host=_HOST, port=_PORT, log_config=log_config)
