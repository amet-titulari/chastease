from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["web-public"])

# Templates directory: src/chastease/templates
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request):
    auth_allow_local_login = bool(getattr(request.app.state.config, "AUTH_ALLOW_LOCAL_LOGIN", True))
    auth_enable_chaster_login = bool(getattr(request.app.state.config, "AUTH_ENABLE_CHASTER_LOGIN", True))
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "auth_allow_local_login": auth_allow_local_login,
            "auth_enable_chaster_login": auth_enable_chaster_login,
        },
    )


@router.get("/favicon.ico", include_in_schema=False)
def favicon_redirect() -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.ico?v=20260307", status_code=307)


@router.get("/contract", response_class=HTMLResponse)
def contract_shell(request: Request):
    return templates.TemplateResponse(request, "contract.html")
