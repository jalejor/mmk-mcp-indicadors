from fastapi import APIRouter
api_v1 = APIRouter()

# Métricas
from .metrics_routing import metrics_router  # noqa: E402
api_v1.include_router(prefix="/metrics", router=metrics_router)

# Dominancia de mercado
from .dominance_routing import router as dominance_router  # noqa: E402
api_v1.include_router(prefix="/dominance", router=dominance_router)
