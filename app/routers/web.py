import hashlib
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_user import AuthUser
from app.models.contract import Contract
from app.models.hygiene_opening import HygieneOpening
from app.models.llm_profile import LlmProfile
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.seal_history import SealHistory
from app.models.session import Session as SessionModel
from app.models.task import Task

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


# Statuses where the user should be redirected back to the play page
_PLAY_REDIRECT_STATUSES = {"active", "safeword_stopped", "yellow", "red"}


def _redirect_if_active_session(user, db) -> str | None:
    """Return redirect URL if user has a recent session worth showing, else None."""
    if user and user.active_session_id:
        session = db.query(SessionModel).filter(
            SessionModel.id == user.active_session_id,
            SessionModel.status.in_(_PLAY_REDIRECT_STATUSES),
        ).first()
        if session:
            return f"/play/{session.id}"
    return None


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request, db: Session = Depends(get_db)):
    current_user = _get_current_user(request, db)
    if current_user:
        target = _redirect_if_active_session(current_user, db)
        if target:
            return RedirectResponse(url=target, status_code=303)
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

    response = RedirectResponse(url="/experience", status_code=303)
    _set_auth_cookie(response, user.session_token)
    return response


@router.post("/auth/login")
def login(
    request: Request,
    username: str = Form(default=""),
    email: str = Form(default=""),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    normalized_username = username.strip()
    normalized_email = email.strip().lower()
    user = None
    if normalized_username:
        user = db.query(AuthUser).filter(AuthUser.username == normalized_username).first()
    elif normalized_email:
        user = db.query(AuthUser).filter(AuthUser.email == normalized_email).first()
    if user is None or user.password_hash != _hash_password(password, user.password_salt):
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={
                "title": f"{settings.app_name} Landing",
                "current_user": None,
                "auth_error": "Login fehlgeschlagen. Bitte pruefe Nutzername und Passwort.",
            },
            status_code=401,
        )

    if not user.session_token:
        user.session_token = secrets.token_urlsafe(32)
        db.commit()

    target = "/experience"
    play_target = _redirect_if_active_session(user, db)
    if play_target:
        target = play_target
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
    # Legacy endpoint: setup flow has been replaced by the experience onboarding.
    return RedirectResponse(url="/experience", status_code=303)


@router.post("/setup/complete")
def complete_setup(
    request: Request,
    role_style: str = Form(...),
    primary_goal: str = Form(...),
    boundary_note: str = Form(...),
    experience_level: str = Form(default="beginner"),
    wearer_nickname: str = Form(default=""),
    hard_limits: str = Form(default=""),
    penalty_multiplier: float = Form(default=1.0),
    gentle_mode: str = Form(default="false"),
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
    user.setup_wearer_nickname = wearer_nickname.strip()[:80] or user.username
    user.setup_hard_limits = hard_limits.strip()[:1500] or None
    user.setup_penalty_multiplier = max(0.1, min(5.0, float(penalty_multiplier)))
    user.setup_gentle_mode = gentle_mode.lower() in ("true", "on", "1", "enabled")
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
    return RedirectResponse(url="/experience", status_code=303)


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
    wearer_nickname: str = Form(default=""),
    hard_limits: str = Form(default=""),
    penalty_multiplier: float = Form(default=1.0),
    gentle_mode: str = Form(default="false"),
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
    user.setup_wearer_nickname = wearer_nickname.strip()[:80] or user.username
    user.setup_hard_limits = hard_limits.strip()[:1500] or None
    user.setup_penalty_multiplier = max(0.1, min(5.0, float(penalty_multiplier)))
    user.setup_gentle_mode = gentle_mode.lower() in ("true", "on", "1", "enabled")
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
    user.setup_wearer_nickname = None
    user.setup_hard_limits = None
    user.setup_penalty_multiplier = None
    user.setup_gentle_mode = False
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


@router.get("/contract/{session_id}", response_class=HTMLResponse)
def contract_view(session_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session_obj is None:
        return RedirectResponse(url="/experience", status_code=303)
    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    content_text = contract.content_text if contract else "(Kein Vertrag vorhanden)"
    signed_at = None
    if contract and contract.signed_at:
        try:
            signed_at = contract.signed_at.strftime("%d.%m.%Y %H:%M")
        except Exception:
            signed_at = str(contract.signed_at)
    return templates.TemplateResponse(
        request=request,
        name="contract_view.html",
        context={
            "title": f"Vertrag – Session #{session_id}",
            "session_id": session_id,
            "content_text": content_text,
            "signed_at": signed_at,
        },
    )


@router.get("/personas", response_class=HTMLResponse)
def personas_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="personas.html",
        context={"title": f"{settings.app_name} – Personas"},
    )


@router.get("/scenarios", response_class=HTMLResponse)
def scenarios_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="scenarios.html",
        context={"title": f"{settings.app_name} – Scenarios"},
    )


@router.get("/api/settings/summary")
def settings_summary(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()

    session_summary = None
    if user.active_session_id:
        session_obj = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()
        if session_obj:
            active_seal = (
                db.query(SealHistory)
                .filter(SealHistory.session_id == session_obj.id, SealHistory.status == "active")
                .order_by(SealHistory.applied_at.desc())
                .first()
            )
            last_opening = (
                db.query(HygieneOpening)
                .filter(HygieneOpening.session_id == session_obj.id)
                .order_by(HygieneOpening.id.desc())
                .first()
            )

            task_rows = db.query(Task).filter(Task.session_id == session_obj.id).all()
            task_total = len(task_rows)
            task_pending = sum(1 for t in task_rows if t.status == "pending")
            task_completed = sum(1 for t in task_rows if t.status == "completed")
            task_overdue = sum(1 for t in task_rows if t.status == "overdue")
            task_failed = sum(1 for t in task_rows if t.status == "failed")
            task_penalty_total_seconds = sum(int(t.consequence_applied_seconds or 0) for t in task_rows)

            opening_rows = db.query(HygieneOpening).filter(HygieneOpening.session_id == session_obj.id).all()
            hygiene_penalty_total_seconds = sum(int(item.penalty_seconds or 0) for item in opening_rows)
            hygiene_overrun_total_seconds = sum(int(item.overrun_seconds or 0) for item in opening_rows)

            remaining_seconds = None
            if session_obj.lock_end is not None:
                lock_end = session_obj.lock_end
                if lock_end.tzinfo is None:
                    lock_end = lock_end.replace(tzinfo=timezone.utc)
                remaining_seconds = max(0, int((lock_end - datetime.now(timezone.utc)).total_seconds()))

            session_summary = {
                "session_id": session_obj.id,
                "status": session_obj.status,
                "lock_start": str(session_obj.lock_start) if session_obj.lock_start else None,
                "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
                "remaining_seconds": remaining_seconds,
                "timer_frozen": bool(session_obj.timer_frozen),
                "min_duration_seconds": session_obj.min_duration_seconds,
                "max_duration_seconds": session_obj.max_duration_seconds,
                "hygiene_limit_daily": session_obj.hygiene_limit_daily,
                "hygiene_limit_weekly": session_obj.hygiene_limit_weekly,
                "hygiene_limit_monthly": session_obj.hygiene_limit_monthly,
                "active_seal_number": active_seal.seal_number if active_seal else None,
                "last_opening_status": last_opening.status if last_opening else None,
                "last_opening_due_back_at": str(last_opening.due_back_at) if (last_opening and last_opening.due_back_at) else None,
                "task_total": task_total,
                "task_pending": task_pending,
                "task_completed": task_completed,
                "task_overdue": task_overdue,
                "task_failed": task_failed,
                "task_penalty_total_seconds": task_penalty_total_seconds,
                "hygiene_penalty_total_seconds": hygiene_penalty_total_seconds,
                "hygiene_overrun_total_seconds": hygiene_overrun_total_seconds,
            }

    return JSONResponse({
        "username": user.username,
        "experience_level": user.setup_experience_level,
        "style": user.setup_style,
        "goal": user.setup_goal,
        "boundary": user.setup_boundary,
        "session": session_summary,
        "llm": {
            "provider": llm.provider,
            "api_url": llm.api_url or "",
            "chat_model": llm.chat_model or "",
            "vision_model": llm.vision_model or "",
            "profile_active": llm.profile_active,
            "api_key_stored": bool(llm.api_key),
        } if llm else None,
    })


@router.post("/api/settings/llm")
async def update_llm_settings(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if not llm:
        llm = LlmProfile(profile_key="default")
        db.add(llm)
    if "provider" in body:
        llm.provider = str(body["provider"])[:50] or "stub"
    if "api_url" in body:
        llm.api_url = str(body["api_url"])[:500] or None
    if body.get("api_key"):
        llm.api_key = str(body["api_key"])
    if "chat_model" in body:
        llm.chat_model = str(body["chat_model"])[:120] or None
    if "vision_model" in body:
        llm.vision_model = str(body["vision_model"])[:120] or None
    if "profile_active" in body:
        llm.profile_active = bool(body["profile_active"])
    db.commit()
    return JSONResponse({"ok": True})


@router.get("/play/{session_id}", response_class=HTMLResponse)
def play_page(session_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session_obj is None:
        return RedirectResponse(url="/experience", status_code=303)
    user.active_session_id = session_id
    db.commit()
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    return templates.TemplateResponse(
        request=request,
        name="play.html",
        context={
            "title": f"Play Mode \u2013 {settings.app_name}",
            "current_user": user,
            "session_id": session_id,
            "session_status": session_obj.status,
            "ws_token": session_obj.ws_auth_token or "",
            "persona_name": persona.name if persona else "Keyholderin",
            "player_nickname": player.nickname if player else user.username,
            "lock_end": session_obj.lock_end.isoformat() if session_obj.lock_end else None,
            "ws_debug_enabled": settings.play_ws_debug_enabled,
        },
    )


@router.get("/experience", response_class=HTMLResponse)
def experience_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="experience.html",
        context={"title": f"{settings.app_name} Experience", "current_user": user},
    )
