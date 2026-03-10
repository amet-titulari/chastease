import hashlib
import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_user import AuthUser

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")
AUTH_COOKIE_NAME = "chastease_auth"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _get_current_user(request: Request, db: Session) -> AuthUser | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    return db.query(AuthUser).filter(AuthUser.session_token == token).first()


def _set_auth_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 30,
        samesite="lax",
    )


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request, db: Session = Depends(get_db)):
    current_user = _get_current_user(request, db)
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={
            "title": f"{settings.app_name} Landing",
            "current_user": current_user,
            "auth_error": None,
        },
    )


@router.post("/auth/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_username = username.strip()
    normalized_email = email.strip().lower()
    if len(normalized_username) < 3:
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={
                "title": f"{settings.app_name} Landing",
                "current_user": None,
                "auth_error": "Der Nutzername muss mindestens 3 Zeichen haben.",
            },
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={
                "title": f"{settings.app_name} Landing",
                "current_user": None,
                "auth_error": "Das Passwort muss mindestens 8 Zeichen haben.",
            },
            status_code=400,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={
                "title": f"{settings.app_name} Landing",
                "current_user": None,
                "auth_error": "Die Passwoerter stimmen nicht ueberein.",
            },
            status_code=400,
        )

    existing = db.query(AuthUser).filter(or_(AuthUser.username == normalized_username, AuthUser.email == normalized_email)).first()
    if existing:
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={
                "title": f"{settings.app_name} Landing",
                "current_user": None,
                "auth_error": "Nutzername oder E-Mail ist bereits registriert.",
            },
            status_code=400,
        )

    salt = secrets.token_hex(16)
    user = AuthUser(
        username=normalized_username,
        email=normalized_email,
        password_salt=salt,
        password_hash=_hash_password(password, salt),
        session_token=secrets.token_urlsafe(32),
        setup_completed=False,
    )
    db.add(user)
    db.commit()

    response = RedirectResponse(url="/setup", status_code=303)
    _set_auth_cookie(response, user.session_token)
    return response


@router.post("/auth/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_email = email.strip().lower()
    user = db.query(AuthUser).filter(AuthUser.email == normalized_email).first()
    if user is None or user.password_hash != _hash_password(password, user.password_salt):
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={
                "title": f"{settings.app_name} Landing",
                "current_user": None,
                "auth_error": "Login fehlgeschlagen. Bitte pruefe E-Mail und Passwort.",
            },
            status_code=401,
        )

    user.session_token = secrets.token_urlsafe(32)
    db.commit()

    target = "/setup" if not user.setup_completed else "/experience"
    response = RedirectResponse(url=target, status_code=303)
    _set_auth_cookie(response, user.session_token)
    return response


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is not None:
        user.session_token = None
        db.commit()
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    if user.setup_completed:
        return RedirectResponse(url="/experience", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={
            "title": f"{settings.app_name} Setup",
            "current_user": user,
        },
    )


@router.post("/setup/complete")
def complete_setup(
    request: Request,
    role_style: str = Form(...),
    primary_goal: str = Form(...),
    boundary_note: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    user.setup_style = role_style.strip()[:80]
    user.setup_goal = primary_goal.strip()[:120]
    user.setup_boundary = boundary_note.strip()[:1500]
    user.setup_completed = True
    db.commit()
    return RedirectResponse(url="/experience", status_code=303)


@router.get("/testconsole", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": settings.app_name},
    )


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"title": f"{settings.app_name} History"},
    )


@router.get("/contracts", response_class=HTMLResponse)
def contracts_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contracts.html",
        context={"title": f"{settings.app_name} Contracts"},
    )


@router.get("/experience", response_class=HTMLResponse)
def experience_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    if not user.setup_completed:
        return RedirectResponse(url="/setup", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="experience.html",
        context={"title": f"{settings.app_name} Experience"},
    )
