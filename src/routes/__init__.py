from fastapi import APIRouter, Depends

from security import api_key_dependency

from .healthy import healthy_router
from .v1 import api_v1

routes = APIRouter()

# Health endpoints stay public.
routes.include_router(healthy_router)

# Every /v1/* endpoint enforces the API key (only when API_KEYS is set).
routes.include_router(
    router=api_v1,
    prefix='/v1',
    dependencies=[Depends(api_key_dependency)],
)
