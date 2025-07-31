from fastapi import APIRouter, Query
from devops_py_utils.web.middlewares import has_errors
from controllers.metrics.dominance_service import DominanceService

router = APIRouter()

tags = ["dominance"]


@router.get("/", tags=tags)
@has_errors
async def get_dominance(
    coins: str = Query("btc,eth", description="Lista de monedas separadas por coma: btc,eth,usdt,bnb"),
    exchange: str = Query("binance", description="Exchange a usar para análisis de indicadores"),
    timeframe: str = Query("daily", description="Marco temporal para indicadores: daily, weekly, etc."),
    limit: int = Query(500, description="Número de velas para indicadores"),
):
    symbols = [c.strip() for c in coins.split(",") if c.strip()]

    # 1. Dominancia global
    dominance = DominanceService().fetch(symbols)

    # 2. Análisis de indicadores por par VS USDT
    from controllers.metrics.metrics_controller import MetricsController
    controller = MetricsController(exchange=exchange)
    analysis = {}
    for s in symbols:
        pair = f"{s.upper()}/USDT"
        try:
            analysis[s.lower()] = controller.process_symbol(symbol=pair, timeframe=timeframe, limit=limit)
        except Exception as e:
            analysis[s.lower()] = {"error": str(e)}

    return {
        "dominance": dominance,
        "analysis": analysis,
    }
