from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["web-app"])

# Templates directory: src/chastease/templates
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/app", response_class=HTMLResponse)
def app_shell(request: Request):
    session_kill_enabled = bool(getattr(request.app.state.config, "ENABLE_SESSION_KILL", False))
    return templates.TemplateResponse(request, "app.html", {"session_kill_enabled": session_kill_enabled})
