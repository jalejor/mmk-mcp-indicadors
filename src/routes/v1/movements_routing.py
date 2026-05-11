from typing import Literal

from fastapi import APIRouter, Query
from middlewares import has_errors

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
    risk_per_trade_pct: float = Query(1.5, description="% del capital arriesgado por trade (sólo si use_atr_sizing=true)"),
    use_atr_sizing: bool = Query(True, description="Si true, los TP/SL se derivan de ATR + R-multiple; si false, se usan los porcentajes fijos del legacy mode"),
):
    """Genera recomendaciones de posiciones long/short en base a indicadores."""
    svc = MovementsService(
        symbol=symbol,
        timeframe=timeframe,
        exchange=exchange,
        capital=capital,
        risk_profile=risk_profile,  # type: ignore[arg-type]
        side=side,  # type: ignore[arg-type]
        risk_per_trade_pct=risk_per_trade_pct,
        use_atr_sizing=use_atr_sizing,
    )
    return svc.execute()
