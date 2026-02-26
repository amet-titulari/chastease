from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["web-app"])

# Templates directory: src/chastease/templates
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/app", response_class=HTMLResponse)
def app_shell(request: Request):
    session_kill_enabled = bool(getattr(request.app.state.config, "ENABLE_SESSION_KILL", False))
    audit_log_enabled = bool(getattr(request.app.state.config, "ENABLE_AUDIT_LOG_VIEW", False))
    return templates.TemplateResponse(
        request,
        "app.html",
        {"session_kill_enabled": session_kill_enabled, "audit_log_enabled": audit_log_enabled},
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_view(request: Request):
    session_kill_enabled = bool(getattr(request.app.state.config, "ENABLE_SESSION_KILL", False))
    audit_log_enabled = bool(getattr(request.app.state.config, "ENABLE_AUDIT_LOG_VIEW", False))
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"session_kill_enabled": session_kill_enabled, "audit_log_enabled": audit_log_enabled},
    )


@router.get("/audit-log", response_class=HTMLResponse)
def audit_log_view(request: Request, session_id: str | None = None):
    audit_log_enabled = bool(getattr(request.app.state.config, "ENABLE_AUDIT_LOG_VIEW", False))
    if not audit_log_enabled:
        raise HTTPException(status_code=404, detail="Not found.")
    return templates.TemplateResponse(
        request,
        "audit_log.html",
        {"session_id": session_id},
    )


@router.get("/turn-log", response_class=HTMLResponse)
def turn_log_view(request: Request, session_id: str | None = None):
    audit_log_enabled = bool(getattr(request.app.state.config, "ENABLE_AUDIT_LOG_VIEW", False))
    if not audit_log_enabled:
        raise HTTPException(status_code=404, detail="Not found.")
    return templates.TemplateResponse(
        request,
        "turn_log.html",
        {"session_id": session_id},
    )


@router.get("/setup", response_class=HTMLResponse)
def setup_view(request: Request, setup_session_id: str | None = None):
    session_kill_enabled = bool(getattr(request.app.state.config, "ENABLE_SESSION_KILL", False))
    audit_log_enabled = bool(getattr(request.app.state.config, "ENABLE_AUDIT_LOG_VIEW", False))
    return templates.TemplateResponse(
        request,
        "setup.html",
        {
            "session_kill_enabled": session_kill_enabled,
            "audit_log_enabled": audit_log_enabled,
            "setup_session_id": setup_session_id,
        },
    )
