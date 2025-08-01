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
