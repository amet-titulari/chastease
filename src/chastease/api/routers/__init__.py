from .auth import router as auth_router
from .chat import router as chat_router
from .llm import router as llm_router
from .setup import router as setup_router
from .sessions import router as sessions_router
from .story import router as story_router
from .system import router as system_router
from .ttlock import router as ttlock_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "chat_router",
    "llm_router",
    "setup_router",
    "sessions_router",
    "users_router",
    "story_router",
    "system_router",
    "ttlock_router",
]
