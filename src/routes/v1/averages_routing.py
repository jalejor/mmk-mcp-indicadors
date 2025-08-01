from datetime import datetime
from typing import List

from fastapi import APIRouter, Query
from devops_py_utils.web.middlewares import has_errors

from controllers.metrics.averages_service import AveragesService

averages_router = APIRouter()

tags = ["averages"]


@averages_router.get("/", tags=tags)
@has_errors
async def get_averages(
    symbol: str = Query(..., description="Par de trading, ej: BTC/USDT"),
    timeframe: str = Query("1h", description="Marco temporal ccxt"),
    exchange: str = Query("binance", description="Exchange a usar"),
    start: datetime | None = Query(None, description="Fecha/hora inicial en formato ISO 8601"),
    end: datetime | None = Query(None, description="Fecha/hora final en formato ISO 8601"),
    span: str = Query("1d", description="Rango retrospectivo si no se provee start/end. Ej: 48h,7d,1w,1m"),
    indicators: str | None = Query(None, description="Indicadores separados por coma: close,rsi,adx,volume"),
    top_n: int = Query(10, ge=1, le=100, description="Número de valores extremos a considerar para highest_prices/lowest_prices y sus promedios"),
):
    """Calcula el promedio de indicadores y detecta el mayor rebote en el rango.

    Parámetros
    ----------
    symbol : str
        Par de trading (BTC/USDT, ETH/USDT, etc.)
    timeframe : str
        Marco temporal ccxt (1m, 5m, 1h, 1d, ...)
    start, end : datetime
        Rango temporal a analizar.
    indicators : str, opcional
        Lista de indicadores separados por coma. Si se omite se calculan los
        soportados por defecto.

    Devuelve
    --------
    dict
        Ver ejemplo de respuesta en la documentación del proyecto.
    """
    indicator_list: List[str] | None = None
    if indicators:
        indicator_list = [ind.strip().lower() for ind in indicators.split(",") if ind.strip()]

    svc = AveragesService(
        symbol=symbol,
        timeframe=timeframe,
        exchange=exchange,
        start=start,
        end=end,
        span=span,
        indicators=indicator_list,
        top_n=top_n,
    )
    return svc.execute()
