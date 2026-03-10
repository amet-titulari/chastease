from pathlib import Path
from contextlib import asynccontextmanager
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
from app.routers import chat, health, hygiene, personas, safety, sessions, tasks, verification as verification_router, web
from app.services.proactive_messaging import sweep_proactive_messages_for_active_sessions
from app.services.session_timer_sweeper import sweep_expired_active_sessions
from app.services.task_sweeper import sweep_overdue_tasks_for_active_sessions


scheduler: BackgroundScheduler | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_app_storage()
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler(timezone="UTC")
        if settings.task_overdue_sweeper_enabled:
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
        if settings.session_timer_sweeper_enabled:
            scheduler.add_job(
                sweep_expired_active_sessions,
                "interval",
                seconds=settings.session_timer_sweeper_interval_seconds,
                id="session_timer_sweeper",
                replace_existing=True,
            )

        if scheduler.get_jobs():
            scheduler.start()
        else:
            scheduler = None
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


def _error_response(status_code: int, code: str, message: str, details=None) -> JSONResponse:
    payload = {
        "request_id": uuid4().hex[:12],
        "error": {
            "code": code,
            "message": message,
        },
        "detail": message,
    }
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
    else:
        message = "Request failed"
    return _error_response(
        status_code=exc.status_code,
        code="http_error",
        message=message,
        details=detail if not isinstance(detail, str) else None,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return _error_response(
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(_: Request, exc: Exception):
    if settings.debug:
        return _error_response(
            status_code=500,
            code="internal_error",
            message=str(exc),
        )
    return _error_response(
        status_code=500,
        code="internal_error",
        message="Internal server error",
    )


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
app.include_router(personas.router)
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(hygiene.router)
app.include_router(safety.router)
app.include_router(verification_router.router)
app.include_router(web.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
