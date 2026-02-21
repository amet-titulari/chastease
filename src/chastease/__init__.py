from fastapi import FastAPI

from .api.routes import api_router
from .config import Config


def create_app(config_object: type[Config] = Config) -> FastAPI:
    app = FastAPI(title="chastease-api", version="0.0.4")
    app.state.config = config_object()
    app.include_router(api_router, prefix="/api/v1")
    return app
