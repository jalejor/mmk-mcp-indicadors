from fastapi import APIRouter
from controllers import healthy_controller
from os import getenv

healthy_router = APIRouter()

tags = ["healthy"]

_HEALTHY_PATH = getenv("HEALTHY_PATH", "/healthy")
_LIVENESS_PATH = getenv("LIVENESS_PATH", "/liveness")


@healthy_router.get('/', tags=tags, include_in_schema=False)
async def root():
    return healthy_controller.root()


@healthy_router.get(_HEALTHY_PATH, tags=tags, include_in_schema=False)
async def healthy():
    return healthy_controller.healthy()


@healthy_router.get(_LIVENESS_PATH, tags=tags, include_in_schema=False)
async def liveness():
    return healthy_controller.liveness()
