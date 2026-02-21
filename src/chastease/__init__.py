from fastapi import FastAPI
from dotenv import load_dotenv

from .api.routes import api_router
from .config import Config
from .db import build_engine, build_session_factory, init_db
from .services.ai.factory import build_ai_service
from .web.routes import web_router


def create_app(config_object: type[Config] = Config) -> FastAPI:
    load_dotenv()
    app = FastAPI(title="chastease-api", version="0.0.5")
    app.state.config = config_object()
    app.state.engine = build_engine(app.state.config.DATABASE_URL)
    app.state.db_session_factory = build_session_factory(app.state.engine)
    init_db(app.state.engine)
    app.state.ai_service = build_ai_service(app.state.config)
    app.include_router(web_router)
    app.include_router(api_router, prefix="/api/v1")
    return app
