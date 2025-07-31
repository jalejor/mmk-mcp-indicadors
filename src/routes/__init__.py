from fastapi import APIRouter
from .healthy import healthy_router
from .v1 import api_v1

routes = APIRouter()

routes.include_router(healthy_router)
routes.include_router(router=api_v1, prefix='/v1')
