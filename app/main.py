from pathlib import Path
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

from app.config import settings
from app.models import (  # noqa: F401
    contract,
    hygiene_opening,
    message,
    persona,
    player_profile,
    safety_log,
    seal_history,
    session,
    task,
    verification,
)
from app.routers import chat, health, hygiene, safety, sessions, tasks, verification as verification_router, web
from app.services.proactive_messaging import sweep_proactive_messages_for_active_sessions
from app.services.task_sweeper import sweep_overdue_tasks_for_active_sessions


scheduler: BackgroundScheduler | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_app_storage()
    global scheduler
    if settings.task_overdue_sweeper_enabled and scheduler is None:
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(
            sweep_overdue_tasks_for_active_sessions,
            "interval",
            seconds=settings.task_overdue_sweeper_interval_seconds,
            id="task_overdue_sweeper",
            replace_existing=True,
        )
        if settings.proactive_messages_enabled:
            scheduler.add_job(
                sweep_proactive_messages_for_active_sessions,
                "interval",
                seconds=settings.proactive_messages_interval_seconds,
                id="proactive_message_sweeper",
                replace_existing=True,
            )
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None


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
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(hygiene.router)
app.include_router(safety.router)
app.include_router(verification_router.router)
app.include_router(web.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
