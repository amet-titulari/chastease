from fastapi import APIRouter

from chastease.api.routes import api_router


def build_backend_router() -> APIRouter:
    router = APIRouter()
    router.include_router(api_router, prefix="/api/v1")
    return router
