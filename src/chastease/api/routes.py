from fastapi import APIRouter

from chastease.api.routers import (
    auth_router,
    chaster_router,
    chat_router,
    llm_router,
    sessions_router,
    setup_router,
    story_router,
    system_router,
    ttlock_router,
    users_router,
    audit_router,
)

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(llm_router)
api_router.include_router(users_router)
api_router.include_router(story_router)
api_router.include_router(chat_router)
api_router.include_router(setup_router)
api_router.include_router(ttlock_router)
api_router.include_router(chaster_router)
api_router.include_router(sessions_router)
api_router.include_router(system_router)
api_router.include_router(audit_router)
