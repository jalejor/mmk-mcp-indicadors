import logging
import functools
from fastapi.responses import JSONResponse

_LOGGER = logging.getLogger(__name__)


def has_errors(func):
    """Decorador que captura excepciones y devuelve un JSON de error estructurado."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            _LOGGER.warning("Validation error in %s: %s", func.__name__, e)
            return JSONResponse(status_code=400, content={"error": str(e)})
        except Exception as e:
            _LOGGER.exception("Unexpected error in %s", func.__name__)
            return JSONResponse(status_code=500, content={"error": str(e)})
    return wrapper
