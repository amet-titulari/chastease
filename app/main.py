from pathlib import Path
from contextlib import asynccontextmanager
from uuid import uuid4
import logging
import sys
import traceback

from apscheduler.schedulers.background import BackgroundScheduler
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

from app.config import settings
from app.release import APP_VERSION
from app.models import (  # noqa: F401
    auth_user,
    contract,
    game_module_setting,
    game_posture_module_assignment,
    game_posture_template,
    game_run,
    game_run_step,
    hygiene_opening,
    item,
    media_asset,
    message,
    persona,
    persona_task_template,
    player_profile,
    safety_log,
    scenario_item,
    seal_history,
    scenario,
    session,
    session_item,
    task,
    verification,
)
from app.routers import chat, games, health, hygiene, inventory, inventory_postures, lovense, media, personas, push, safety, scenarios, sessions, tasks, verification as verification_router, voice, web
from app.security import CSRF_COOKIE_NAME, SAFE_HTTP_METHODS, csrf_tokens_match, extract_csrf_token, generate_csrf_token, is_cookie_secure, is_same_origin_request
from app.services.media_retention import prune_expired_verification_media
from app.services.proactive_messaging import sweep_proactive_messages_for_active_sessions
from app.services.request_limits import check_request_limit
from app.services.session_timer_sweeper import sweep_expired_active_sessions
from app.services.task_sweeper import sweep_overdue_tasks_for_active_sessions


scheduler: BackgroundScheduler | None = None
logger = logging.getLogger("uvicorn.error")


def validate_runtime_configuration() -> None:
    if settings.debug or settings.allow_insecure_dev_mode:
        return
    if not str(settings.secret_encryption_key or "").strip():
        raise RuntimeError(
            "CHASTEASE_SECRET_ENCRYPTION_KEY is required unless CHASTEASE_DEBUG=true "
            "or CHASTEASE_ALLOW_INSECURE_DEV_MODE=true is set."
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_configuration()
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
        if settings.verification_media_retention_enabled:
            scheduler.add_job(
                prune_expired_verification_media,
                "interval",
                hours=1,
                id="verification_media_retention",
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


app = FastAPI(title=settings.app_name, version=APP_VERSION, debug=settings.debug, lifespan=lifespan)


@app.middleware("http")
async def request_throttle_middleware(request: Request, call_next):
    allowed, rule = check_request_limit(request)
    if not allowed and rule is not None:
        return _error_response(
            status_code=429,
            code="rate_limited",
            message=f"Zu viele Anfragen fuer {rule.key}. Bitte kurz warten.",
            details={"window_seconds": rule.window_seconds, "max_requests": rule.max_requests},
        )
    return await call_next(request)


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    request.state.csrf_token = csrf_cookie or generate_csrf_token()

    if request.method.upper() not in SAFE_HTTP_METHODS:
        request_token = await extract_csrf_token(request)
        if request_token:
            if not csrf_tokens_match(csrf_cookie, request_token):
                return _error_response(status_code=403, code="csrf_failed", message="CSRF validation failed")
        else:
            same_origin = is_same_origin_request(request)
            if same_origin is False:
                return _error_response(status_code=403, code="csrf_failed", message="CSRF validation failed")

    response = await call_next(request)

    if request.method.upper() in SAFE_HTTP_METHODS and not csrf_cookie:
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=request.state.csrf_token,
            httponly=False,
            max_age=60 * 60 * 24 * 30,
            samesite="lax",
            secure=is_cookie_secure(),
        )
    return response


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
async def unexpected_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    print(f"[internal_error] {request.method} {request.url.path}", file=sys.stderr, flush=True)
    traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
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
validate_runtime_configuration()
init_app_storage()


app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(personas.router)
app.include_router(scenarios.router)
app.include_router(push.router)
app.include_router(chat.router)
app.include_router(games.router)
app.include_router(tasks.router)
app.include_router(hygiene.router)
app.include_router(safety.router)
app.include_router(verification_router.router)
app.include_router(inventory.router)
app.include_router(inventory_postures.router)
app.include_router(media.router)
app.include_router(voice.router)
app.include_router(lovense.router)
app.include_router(web.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
