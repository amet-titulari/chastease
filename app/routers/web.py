import hashlib
import secrets

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_user import AuthUser
from app.models.llm_profile import LlmProfile

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

    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={
            "title": f"{settings.app_name} Setup",
            "current_user": user,
            "llm": llm,
        },
    )


@router.post("/setup/complete")
def complete_setup(
    request: Request,
    role_style: str = Form(...),
    primary_goal: str = Form(...),
    boundary_note: str = Form(...),
    experience_level: str = Form(default="beginner"),
    llm_provider: str = Form(default="stub"),
    llm_api_url: str = Form(default=""),
    llm_api_key: str = Form(default=""),
    llm_chat_model: str = Form(default=""),
    llm_vision_model: str = Form(default=""),
    llm_active: str = Form(default="false"),
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    user.setup_style = role_style.strip()[:80]
    user.setup_goal = primary_goal.strip()[:120]
    user.setup_boundary = boundary_note.strip()[:1500]
    user.setup_experience_level = experience_level.strip()[:50] if experience_level.strip() in ("beginner", "intermediate", "advanced") else "beginner"
    user.setup_completed = True
    db.commit()

    if llm_provider.strip() not in ("", "stub") or llm_api_url.strip() or llm_chat_model.strip():
        llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
        if not llm:
            llm = LlmProfile(profile_key="default")
            db.add(llm)
        llm.provider = llm_provider.strip()[:50] or "stub"
        llm.api_url = llm_api_url.strip()[:500] or None
        if llm_api_key.strip():
            llm.api_key = llm_api_key.strip()
        llm.chat_model = llm_chat_model.strip()[:120] or None
        llm.vision_model = llm_vision_model.strip()[:120] or None
        llm.profile_active = llm_active.lower() in ("true", "on", "1", "enabled")
        db.commit()

    return RedirectResponse(url="/experience", status_code=303)


@router.post("/setup/test-llm")
async def setup_test_llm(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    body = await request.json()
    api_url = str(body.get("api_url", "")).strip()
    api_key = str(body.get("api_key", "")).strip()
    chat_model = str(body.get("chat_model", "")).strip()
    if not api_url or not chat_model:
        return JSONResponse({"ok": False, "error": "API URL und Chat-Modell sind Pflichtfelder."})
    if not api_key:
        stored = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
        if stored and stored.api_key:
            api_key = stored.api_key
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                api_url,
                headers=headers,
                json={"model": chat_model, "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 5},
            )
        resp.raise_for_status()
        return JSONResponse({"ok": True, "status": resp.status_code})
    except httpx.HTTPStatusError as exc:
        return JSONResponse({"ok": False, "error": f"HTTP {exc.response.status_code}"})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)[:200]})


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "title": f"{settings.app_name} Profile",
            "current_user": user,
            "profile_message": None,
            "profile_error": None,
            "llm": llm,
            "llm_message": None,
            "llm_error": None,
        },
    )


@router.get("/profile/llm/status")
def llm_status(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if not llm:
        return JSONResponse({"ready": False, "api_key_stored": False, "profile_active": False})
    return JSONResponse({
        "ready": bool(llm.profile_active and llm.api_url and llm.chat_model),
        "api_key_stored": bool(llm.api_key),
        "profile_active": llm.profile_active,
        "provider": llm.provider,
        "api_url": llm.api_url,
        "chat_model": llm.chat_model,
        "vision_model": llm.vision_model,
    })


@router.post("/profile/llm")
def save_llm_profile(
    request: Request,
    provider: str = Form(default="stub"),
    api_url: str = Form(default=""),
    api_key: str = Form(default=""),
    chat_model: str = Form(default=""),
    vision_model: str = Form(default=""),
    profile_active: str = Form(default="false"),
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if not llm:
        llm = LlmProfile(profile_key="default")
        db.add(llm)

    llm.provider = provider.strip()[:50] or "stub"
    llm.api_url = api_url.strip()[:500] or None
    if api_key.strip():
        llm.api_key = api_key.strip()
    llm.chat_model = chat_model.strip()[:120] or None
    llm.vision_model = vision_model.strip()[:120] or None
    llm.profile_active = profile_active.lower() in ("true", "on", "1", "enabled")
    db.commit()

    llm2 = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "title": f"{settings.app_name} Profile",
            "current_user": user,
            "profile_message": None,
            "profile_error": None,
            "llm": llm2,
            "llm_message": "LLM-Profil gespeichert.",
            "llm_error": None,
        },
    )


@router.post("/profile/llm/test")
async def test_llm_profile(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if not llm or not llm.api_url or not llm.chat_model:
        return JSONResponse({"ok": False, "error": "Kein LLM-Profil konfiguriert."})
    try:
        headers = {"Content-Type": "application/json"}
        if llm.api_key:
            headers["Authorization"] = f"Bearer {llm.api_key}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                llm.api_url,
                headers=headers,
                json={"model": llm.chat_model, "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 5},
            )
        resp.raise_for_status()
        return JSONResponse({"ok": True, "status": resp.status_code})
    except httpx.HTTPStatusError as exc:
        return JSONResponse({"ok": False, "error": f"HTTP {exc.response.status_code}"})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)[:200]})


@router.post("/profile/setup")
def update_profile_setup(
    request: Request,
    role_style: str = Form(...),
    primary_goal: str = Form(...),
    boundary_note: str = Form(...),
    experience_level: str = Form(default="beginner"),
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    style = role_style.strip()[:80]
    goal = primary_goal.strip()[:120]
    boundary = boundary_note.strip()[:1500]
    if not style or not goal:
        llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
        return templates.TemplateResponse(
            request=request,
            name="profile.html",
            context={
                "title": f"{settings.app_name} Profile",
                "current_user": user,
                "profile_message": None,
                "profile_error": "Leitstil und Ziel duerfen nicht leer sein.",
                "llm": llm,
                "llm_message": None,
                "llm_error": None,
            },
            status_code=400,
        )

    user.setup_style = style
    user.setup_goal = goal
    user.setup_boundary = boundary
    user.setup_experience_level = experience_level.strip()[:50] if experience_level.strip() in ("beginner", "intermediate", "advanced") else "beginner"
    user.setup_completed = True
    db.commit()
    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "title": f"{settings.app_name} Profile",
            "current_user": user,
            "profile_message": "Setup-Daten wurden aktualisiert.",
            "profile_error": None,
            "llm": llm,
            "llm_message": None,
            "llm_error": None,
        },
    )


@router.post("/profile/restart-setup")
def restart_setup(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    user.setup_completed = False
    user.setup_style = None
    user.setup_goal = None
    user.setup_boundary = None
    db.commit()
    return RedirectResponse(url="/setup", status_code=303)


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
        context={"title": f"{settings.app_name} Experience", "current_user": user},
    )
