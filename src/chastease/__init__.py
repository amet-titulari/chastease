from fastapi import FastAPI
from dotenv import load_dotenv

from .backend import build_backend_router
from .config import Config
from .db import build_engine, build_session_factory, init_db
from .connectors import build_default_tool_registry
from .frontend import build_frontend_router
from .services.ai.factory import build_ai_service


def create_app(config_object: type[Config] = Config) -> FastAPI:
    load_dotenv()
    app = FastAPI(title="chastease-api", version="0.1.0")
    app.state.config = config_object()
    app.state.engine = build_engine(app.state.config.DATABASE_URL)
    app.state.db_session_factory = build_session_factory(app.state.engine)
    init_db(app.state.engine)
    app.state.ai_service = build_ai_service(app.state.config)
    app.state.tool_registry = build_default_tool_registry()
    app.include_router(build_frontend_router())
    app.include_router(build_backend_router())
    return app
