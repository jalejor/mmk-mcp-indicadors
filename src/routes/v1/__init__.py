from fastapi import APIRouter
api_v1 = APIRouter()

# Métricas
from .metrics_routing import metrics_router  # noqa: E402
api_v1.include_router(prefix="/metrics", router=metrics_router)

# Dominancia de mercado
from .dominance_routing import router as dominance_router  # noqa: E402
api_v1.include_router(prefix="/dominance", router=dominance_router)

# Promedios de indicadores
from .averages_routing import averages_router  # noqa: E402
api_v1.include_router(prefix="/averages", router=averages_router)

# Recomendaciones de movimientos
from .movements_routing import movements_router  # noqa: E402
api_v1.include_router(prefix="/movements", router=movements_router)

# Datos para gráficos
from .chart_routing import chart_router  # noqa: E402
api_v1.include_router(prefix="/charts", router=chart_router)

# Precio fresco (ticker) — sin el cache de OHLCV
from .ticker_routing import ticker_router  # noqa: E402
api_v1.include_router(prefix="/ticker", router=ticker_router)

# Backtest engine
from .backtest_routing import backtest_router  # noqa: E402
api_v1.include_router(prefix="/backtest", router=backtest_router)

# Strategy setups (F0 live evaluation)
from .setups_routing import setups_router  # noqa: E402
api_v1.include_router(prefix="/setups", router=setups_router)
