from pathlib import Path
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

from app.config import settings
from app.models import contract, hygiene_opening, message, persona, player_profile, session  # noqa: F401
from app.routers import health, hygiene, sessions, web


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_app_storage()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


def init_app_storage() -> None:
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)

    bootstrap_engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    with bootstrap_engine.connect() as conn:
        has_alembic = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        ).fetchone()
        has_personas = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='personas'")
        ).fetchone()

    alembic_cfg = Config(str(Path("alembic.ini").resolve()))
    if has_personas and not has_alembic:
        command.stamp(alembic_cfg, "20260310_0001")
    command.upgrade(alembic_cfg, "head")


# Initialize immediately so imports in tests have a migrated schema available.
init_app_storage()


app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(hygiene.router)
app.include_router(web.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
