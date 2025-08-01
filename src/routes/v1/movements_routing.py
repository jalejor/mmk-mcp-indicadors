from typing import Literal

from fastapi import APIRouter, Query
from devops_py_utils.web.middlewares import has_errors

from controllers.metrics.movements_service import MovementsService

movements_router = APIRouter()

tags = ["movements"]


@movements_router.get("/", tags=tags)
@has_errors
async def get_movements(
    symbol: str = Query(..., description="Par de trading, ej: BTC/USDT"),
    timeframe: str = Query("1h", description="Marco temporal"),
    exchange: str = Query("binance", description="Exchange"),
    capital: float = Query(1000.0, description="Capital disponible para la posición"),
    risk_profile: Literal["low", "medium", "high"] = Query("medium", description="Perfil de riesgo"),
    side: Literal["long", "short", "both"] = Query("both", description="Tipo de posición a analizar"),
):
    """Genera recomendaciones de posiciones long/short en base a indicadores.

    Input y output documentados en README.
    """
    svc = MovementsService(
        symbol=symbol,
        timeframe=timeframe,
        exchange=exchange,
        capital=capital,
        risk_profile=risk_profile,  # type: ignore[arg-type]
        side=side,  # type: ignore[arg-type]
    )
    return svc.execute()
