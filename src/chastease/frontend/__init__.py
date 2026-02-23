from fastapi import APIRouter

from chastease.web.routes import web_router


def build_frontend_router() -> APIRouter:
    router = APIRouter()
    router.include_router(web_router)
    return router
