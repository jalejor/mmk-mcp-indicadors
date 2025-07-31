from fastapi import APIRouter, Query
from devops_py_utils.web.middlewares import has_errors
from controllers.metrics.metrics_controller import MetricsController

metrics_router = APIRouter()

tags = ["metrics"]


def _get_controller(exchange: str):
    return MetricsController(exchange=exchange)


@metrics_router.get("/get", tags=tags)
@has_errors
async def get_metrics(
    symbol: str = Query(..., description="Par a consultar, ej: BTC/USDT"),
    exchange: str = Query("binance", description="Exchange a usar"),
    timeframe: str = Query("1h", description="Marco temporal"),
    limit: int = Query(500, description="Número de velas"),
):
    controller = _get_controller(exchange)
    return controller.process_symbol(symbol=symbol, timeframe=timeframe, limit=limit)
