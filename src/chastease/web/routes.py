from fastapi import APIRouter

from chastease.web.routers import app_router, chat_router, public_router

web_router = APIRouter()
web_router.include_router(public_router)
web_router.include_router(app_router)
web_router.include_router(chat_router)
