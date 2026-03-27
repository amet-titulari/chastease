import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Form, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_user import AuthUser
from app.models.contract import Contract
from app.models.item import Item
from app.models.game_posture_template import GamePostureTemplate
from app.models.game_run import GameRun
from app.models.hygiene_opening import HygieneOpening
from app.models.llm_profile import LlmProfile
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.scenario import Scenario
from app.models.seal_history import SealHistory
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.routers.personas import PERSONA_PRESETS, get_system_persona_by_key
from app.security import AUTH_COOKIE_NAME, is_cookie_secure
from app.services.access_control import is_admin_user
from app.services.auth_password import hash_password, is_legacy_password_hash, verify_legacy_password, verify_password_and_update
from app.services.contract_service import default_contract_preferences, normalize_contract_preferences
from app.services.games import as_public_module_payload, get_module, list_modules
from app.services.lovense import lovense_status_payload

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")


def _asset_version(relative_path: str) -> str:
    try:
        target = Path("app/static") / relative_path
        return str(int(target.stat().st_mtime))
    except OSError:
        return "dev"


class ExperienceDraftRequest(BaseModel):
    persona_name: str | None = Field(default=None, max_length=120)
    persona_tone: str | None = Field(default=None, max_length=60)
    persona_dominance: str | None = Field(default=None, max_length=60)
    persona_description: str | None = Field(default=None, max_length=4000)
    persona_system_prompt: str | None = Field(default=None, max_length=4000)
    scenario_preset: str | None = Field(default=None, max_length=120)
    wearer_nickname: str | None = Field(default=None, max_length=80)
    experience_level: str | None = Field(default=None, max_length=50)
    hard_limits: str | None = Field(default=None, max_length=1500)
    min_duration_seconds: int | None = Field(default=None, ge=60)
    max_duration_seconds: int | None = Field(default=None, ge=60)
    no_max_limit: bool | None = None
    hygiene_limit_daily: int | None = Field(default=None, ge=0)
    hygiene_limit_weekly: int | None = Field(default=None, ge=0)
    hygiene_limit_monthly: int | None = Field(default=None, ge=0)
    penalty_multiplier: float | None = None
    default_penalty_seconds: int | None = Field(default=None, ge=0)
    max_penalty_seconds: int | None = Field(default=None, ge=0)
    gentle_mode: bool | None = None
    hygiene_opening_max_duration_seconds: int | None = Field(default=None, ge=1)
    seal_enabled: bool | None = None
    initial_seal_number: str | None = Field(default=None, max_length=120)
    contract_keyholder_title: str | None = Field(default=None, max_length=80)
    contract_wearer_title: str | None = Field(default=None, max_length=80)
    contract_goal: str | None = Field(default=None, max_length=4000)
    contract_method: str | None = Field(default=None, max_length=200)
    contract_wearing_schedule: str | None = Field(default=None, max_length=160)
    contract_touch_rules: str | None = Field(default=None, max_length=4000)
    contract_orgasm_rules: str | None = Field(default=None, max_length=4000)
    contract_reward_policy: str | None = Field(default=None, max_length=4000)
    contract_termination_policy: str | None = Field(default=None, max_length=4000)
    llm_provider: str | None = Field(default=None, max_length=50)
    llm_api_url: str | None = Field(default=None, max_length=500)
    llm_api_key: str | None = Field(default=None, max_length=4000)
    llm_chat_model: str | None = Field(default=None, max_length=120)
    llm_vision_model: str | None = Field(default=None, max_length=120)
    llm_active: bool | None = None


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
        secure=is_cookie_secure(),
    )


def _admin_bootstrap_emails() -> set[str]:
    raw = settings.admin_bootstrap_emails or ""
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_admin_user(user: AuthUser | None) -> bool:
    return is_admin_user(user)


def _require_admin_user(request: Request, db: Session) -> AuthUser | RedirectResponse:
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    if not _is_admin_user(user):
        return RedirectResponse(url="/experience", status_code=303)
    return user


# Session statuses that should keep the user in the current play context.
_PLAY_REDIRECT_STATUSES = {
    "pending_contract",
    "active",
    "paused",
    "safeword_stopped",
    "emergency_stopped",
    "yellow",
    "red",
}


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


def _load_json_dict(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _contract_preferences_from_prefs(prefs: dict | None) -> dict:
    if not isinstance(prefs, dict):
        return default_contract_preferences()
    return normalize_contract_preferences(prefs.get("contract"))


def _resolve_default_player_profile(user: AuthUser, db: Session, create_if_missing: bool = False) -> PlayerProfile | None:
    profile = None
    if user.default_player_profile_id:
        profile = db.query(PlayerProfile).filter(PlayerProfile.id == user.default_player_profile_id).first()

    if profile is None and user.active_session_id:
        active_session = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()
        if active_session:
            profile = db.query(PlayerProfile).filter(PlayerProfile.id == active_session.player_profile_id).first()
            if profile:
                user.default_player_profile_id = profile.id
                if profile.auth_user_id is None:
                    profile.auth_user_id = user.id

    if profile is None and create_if_missing:
        profile = PlayerProfile(
            auth_user_id=user.id,
            nickname=user.username,
            experience_level="beginner",
            preferences_json=json.dumps({}),
            hard_limits_json=json.dumps([]),
            reaction_patterns_json=json.dumps({"penalty_multiplier": 1.0}),
            needs_json=json.dumps({"gentle_mode": False}),
        )
        db.add(profile)
        db.flush()
        user.default_player_profile_id = profile.id

    if profile and profile.auth_user_id is None:
        profile.auth_user_id = user.id

    return profile


def _setup_context_from_user_and_profile(user: AuthUser, profile: PlayerProfile | None) -> dict:
    if not profile:
        contract = default_contract_preferences()
        return {
            "wearer_nickname": user.username,
            "experience_level": "beginner",
            "style": "structured",
            "goal": "",
            "boundary": "",
            "hard_limits": "",
            "penalty_multiplier": 1.0,
            "gentle_mode": False,
            "contract": contract,
        }

    prefs = _load_json_dict(profile.preferences_json)
    reaction = _load_json_dict(profile.reaction_patterns_json)
    needs = _load_json_dict(profile.needs_json)
    hard_limits = _load_json_list(profile.hard_limits_json)
    contract = _contract_preferences_from_prefs(prefs)
    return {
        "wearer_nickname": profile.nickname or user.username,
        "experience_level": profile.experience_level or "beginner",
        "style": prefs.get("wearer_style") or "structured",
        "goal": prefs.get("wearer_goal") or "",
        "boundary": prefs.get("wearer_boundary") or "",
        "hard_limits": ", ".join(str(x).strip() for x in hard_limits if str(x).strip()),
        "penalty_multiplier": (
            reaction.get("penalty_multiplier")
            if isinstance(reaction.get("penalty_multiplier"), (int, float))
            else 1.0
        ),
        "gentle_mode": bool(needs.get("gentle_mode", False)),
        "contract": contract,
    }


def _render_profile_page(
    request: Request,
    user: AuthUser,
    db: Session,
    profile_message: str | None = None,
    profile_error: str | None = None,
    llm_message: str | None = None,
    llm_error: str | None = None,
):
    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    default_profile = _resolve_default_player_profile(user, db, create_if_missing=False)
    setup_ctx = _setup_context_from_user_and_profile(user, default_profile)
    active_session = None
    if user.active_session_id:
        active_session = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()

    # Fallback: if no default LLM profile exists, show active session LLM settings instead.
    if llm is None and active_session and any(
        [
            active_session.llm_provider,
            active_session.llm_api_url,
            active_session.llm_chat_model,
            active_session.llm_vision_model,
            active_session.llm_api_key,
        ]
    ):
        llm = {
            "provider": active_session.llm_provider or "custom",
            "api_url": active_session.llm_api_url or "",
            "api_key": active_session.llm_api_key or "",
            "chat_model": active_session.llm_chat_model or "",
            "vision_model": active_session.llm_vision_model or "",
            "profile_active": bool(active_session.llm_profile_active),
        }

    def _llm_field(obj, key: str):
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    active_play_url = _redirect_if_active_session(user, db)

    transcription_api_url = settings.transcription_api_url or ""
    if not transcription_api_url and _llm_field(llm, "api_url"):
        api_url_value = str(_llm_field(llm, "api_url") or "")
        if "/chat/completions" in api_url_value:
            transcription_api_url = api_url_value.replace("/chat/completions", "/audio/transcriptions")

    voice_ws_url = settings.voice_realtime_ws_url or "wss://api.x.ai/v1/realtime"

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "title": f"{settings.app_name} Wearer-Profil",
            "current_user": user,
            "profile_message": profile_message,
            "profile_error": profile_error,
            "llm": llm,
            "llm_message": llm_message,
            "llm_error": llm_error,
            "active_play_url": active_play_url,
            "setup": setup_ctx,
            "audio": {
                "transcription_enabled": bool(settings.transcription_enabled),
                "transcription_api_url": transcription_api_url,
                "transcription_model": settings.transcription_model or "",
                "transcription_language": settings.transcription_language or "",
                "voice_realtime_enabled": bool(settings.voice_realtime_enabled),
                "voice_realtime_mode": settings.voice_realtime_mode or "realtime-manual",
                "voice_realtime_agent_id": settings.voice_realtime_agent_id or "",
                "voice_realtime_ws_url": voice_ws_url,
                "voice_realtime_default_voice": settings.voice_realtime_default_voice or "",
                "transcription_api_key_stored": bool(settings.transcription_api_key),
                "voice_api_key_stored": bool(settings.voice_realtime_api_key),
            },
        },
    )


def _build_settings_summary_payload(
    request: Request,
    user: AuthUser,
    db: Session,
    session_id: int | None = None,
) -> dict:
    llm_default = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    default_profile = _resolve_default_player_profile(user, db, create_if_missing=True)
    default_setup = _setup_context_from_user_and_profile(user, default_profile)
    db.commit()
    profile_experience = None
    profile_style = None
    profile_goal = None
    profile_limits = None
    llm_payload = {
        "provider": llm_default.provider,
        "api_url": llm_default.api_url or "",
        "chat_model": llm_default.chat_model or "",
        "vision_model": llm_default.vision_model or "",
        "profile_active": llm_default.profile_active,
        "api_key_stored": bool(llm_default.api_key),
    } if llm_default else None

    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    total_played_seconds = 0
    owned_profiles = db.query(PlayerProfile.id).filter(PlayerProfile.auth_user_id == user.id).all()
    owned_profile_ids = [row.id for row in owned_profiles]
    if owned_profile_ids:
        owned_sessions = db.query(SessionModel).filter(SessionModel.player_profile_id.in_(owned_profile_ids)).all()
        now_utc = datetime.now(timezone.utc)
        for owned_session in owned_sessions:
            lock_start = _as_utc(owned_session.lock_start)
            if lock_start is None:
                continue
            end_anchor = _as_utc(owned_session.lock_end_actual) or now_utc
            total_played_seconds += max(0, int((end_anchor - lock_start).total_seconds()))

    session_summary = None
    target_session_id = session_id or user.active_session_id
    if target_session_id:
        session_obj = db.query(SessionModel).filter(SessionModel.id == target_session_id).first()
        if session_obj:
            persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
            player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
            prefs = {}
            reaction = {}
            hard_limits: list[str] = []
            if player:
                try:
                    parsed_prefs = json.loads(player.preferences_json or "{}")
                    if isinstance(parsed_prefs, dict):
                        prefs = parsed_prefs
                except Exception:
                    prefs = {}
                try:
                    parsed_limits = json.loads(player.hard_limits_json or "[]")
                    if isinstance(parsed_limits, list):
                        hard_limits = [str(x) for x in parsed_limits if str(x).strip()]
                except Exception:
                    hard_limits = []
                try:
                    parsed_reaction = json.loads(player.reaction_patterns_json or "{}")
                    if isinstance(parsed_reaction, dict):
                        reaction = parsed_reaction
                except Exception:
                    reaction = {}

            effective_hygiene_min_penalty = settings.hygiene_overdue_penalty_seconds
            if isinstance(reaction.get("default_penalty_seconds"), (int, float)) and int(reaction.get("default_penalty_seconds")) > 0:
                effective_hygiene_min_penalty = int(reaction.get("default_penalty_seconds"))

            if player:
                profile_experience = player.experience_level or default_setup["experience_level"]
                profile_style = prefs.get("wearer_style") or default_setup["style"]
                profile_goal = prefs.get("wearer_goal") or default_setup["goal"]
                boundary = prefs.get("wearer_boundary")
                if boundary and hard_limits:
                    hard_limits_str = ", ".join(hard_limits)
                    if str(boundary).strip().lower() == hard_limits_str.strip().lower():
                        profile_limits = hard_limits_str
                    else:
                        profile_limits = f"{boundary} | Hard Limits: {hard_limits_str}"
                elif boundary:
                    profile_limits = boundary
                elif hard_limits:
                    profile_limits = ", ".join(hard_limits)
            else:
                profile_experience = default_setup["experience_level"]
                profile_style = default_setup["style"]
                profile_goal = default_setup["goal"]
                profile_limits = default_setup["hard_limits"] or default_setup["boundary"]

            llm_payload = {
                "provider": session_obj.llm_provider or (llm_default.provider if llm_default else ""),
                "api_url": session_obj.llm_api_url or (llm_default.api_url if llm_default else ""),
                "chat_model": session_obj.llm_chat_model or (llm_default.chat_model if llm_default else ""),
                "vision_model": session_obj.llm_vision_model or (llm_default.vision_model if llm_default else ""),
                "profile_active": bool(session_obj.llm_profile_active),
                "api_key_stored": bool(session_obj.llm_api_key or (llm_default.api_key if llm_default else None)),
            }

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
                "persona_name": persona.name if persona else "Keyholderin",
                "persona_avatar_media_id": persona.avatar_media_id if persona else None,
                "persona_avatar_url": (f"/api/media/{persona.avatar_media_id}/content" if (persona and persona.avatar_media_id) else None),
                "player_nickname": player.nickname if player else None,
                "player_avatar_media_id": player.avatar_media_id if player else None,
                "player_avatar_url": (f"/api/media/{player.avatar_media_id}/content" if (player and player.avatar_media_id) else None),
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
                "hygiene_overdue_penalty_min_seconds": effective_hygiene_min_penalty,
                "total_played_seconds": total_played_seconds,
                "hygiene_opening_max_duration_seconds": (
                    session_obj.hygiene_opening_max_duration_seconds
                    if session_obj.hygiene_opening_max_duration_seconds is not None
                    else (
                        (
                            prefs.get("hygiene_opening_max_duration_seconds")
                            if isinstance(prefs.get("hygiene_opening_max_duration_seconds"), (int, float))
                            and int(prefs.get("hygiene_opening_max_duration_seconds")) > 0
                            else settings.hygiene_opening_max_duration_seconds
                        )
                    )
                ),
            }

    if profile_experience is None:
        profile_experience = default_setup["experience_level"]
    if profile_style is None:
        profile_style = default_setup["style"]
    if profile_goal is None:
        profile_goal = default_setup["goal"]
    if profile_limits is None:
        profile_limits = default_setup["hard_limits"] or default_setup["boundary"]

    return {
        "username": user.username,
        "experience_level": profile_experience,
        "style": profile_style,
        "goal": profile_goal,
        "boundary": profile_limits,
        "session": session_summary,
        "llm": llm_payload,
    }


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

    bootstrap_emails = _admin_bootstrap_emails()
    existing_admin = db.query(AuthUser.id).filter(AuthUser.is_admin == True).first()  # noqa: E712
    should_be_admin = existing_admin is None or normalized_email in bootstrap_emails

    user = AuthUser(
        username=normalized_username,
        email=normalized_email,
        password_salt="",
        password_hash=hash_password(password),
        session_token=secrets.token_urlsafe(32),
        is_admin=should_be_admin,
        setup_completed=False,
    )
    db.add(user)
    db.flush()

    profile = PlayerProfile(
        auth_user_id=user.id,
        nickname=user.username,
        experience_level="beginner",
        preferences_json=json.dumps({}),
        soft_limits_json=json.dumps([]),
        hard_limits_json=json.dumps([]),
        reaction_patterns_json=json.dumps({"penalty_multiplier": 1.0}),
        needs_json=json.dumps({"gentle_mode": False}),
    )
    db.add(profile)
    db.flush()
    user.default_player_profile_id = profile.id
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
    password_valid = False
    password_upgraded = False
    if user is not None:
        if is_legacy_password_hash(user.password_hash):
            password_valid = verify_legacy_password(password, user.password_hash, user.password_salt)
            if password_valid:
                user.password_hash = hash_password(password)
                user.password_salt = ""
                password_upgraded = True
        else:
            password_valid, updated_hash = verify_password_and_update(password, user.password_hash)
            if password_valid and updated_hash:
                user.password_hash = updated_hash
                password_upgraded = True

    if user is None or not password_valid:
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
        password_upgraded = True

    if password_upgraded:
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
    response.delete_cookie(AUTH_COOKIE_NAME, samesite="lax", secure=is_cookie_secure())
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

    style = role_style.strip()[:80]
    goal = primary_goal.strip()[:120]
    boundary = boundary_note.strip()[:1500]
    level = experience_level.strip()[:50] if experience_level.strip() in ("beginner", "intermediate", "advanced") else "beginner"
    nickname = wearer_nickname.strip()[:80] or user.username
    limits = [part.strip() for part in hard_limits.split(",") if part.strip()]
    penalty = max(0.1, min(5.0, float(penalty_multiplier)))
    gentle = gentle_mode.lower() in ("true", "on", "1", "enabled")
    user.setup_completed = True

    profile = _resolve_default_player_profile(user, db, create_if_missing=True)
    if profile:
        profile.nickname = nickname
        profile.experience_level = level
        prefs = _load_json_dict(profile.preferences_json)
        prefs["wearer_style"] = style
        prefs["wearer_goal"] = goal
        prefs["wearer_boundary"] = boundary
        profile.preferences_json = json.dumps(prefs)
        profile.hard_limits_json = json.dumps(limits)
        reaction = _load_json_dict(profile.reaction_patterns_json)
        reaction["penalty_multiplier"] = penalty
        profile.reaction_patterns_json = json.dumps(reaction)
        needs = _load_json_dict(profile.needs_json)
        needs["gentle_mode"] = gentle
        profile.needs_json = json.dumps(needs)
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
    _resolve_default_player_profile(user, db, create_if_missing=True)
    db.commit()
    return _render_profile_page(request=request, user=user, db=db)


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
    return _render_profile_page(
        request=request,
        user=user,
        db=db,
        llm_message="KI-Profil gespeichert.",
    )


@router.post("/profile/llm/test")
async def test_llm_profile(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if not llm or not llm.api_url or not llm.chat_model:
        return JSONResponse({"ok": False, "error": "Kein KI-Profil konfiguriert."})
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
        return _render_profile_page(
            request=request,
            user=user,
            db=db,
            profile_error="Leitstil und Ziel duerfen nicht leer sein.",
        )

    level = experience_level.strip()[:50] if experience_level.strip() in ("beginner", "intermediate", "advanced") else "beginner"
    nickname = wearer_nickname.strip()[:80] or user.username
    limits = [part.strip() for part in hard_limits.split(",") if part.strip()]
    penalty = max(0.1, min(5.0, float(penalty_multiplier)))
    gentle = gentle_mode.lower() in ("true", "on", "1", "enabled")
    user.setup_completed = True

    profile = _resolve_default_player_profile(user, db, create_if_missing=True)
    if profile:
        profile.nickname = nickname
        profile.experience_level = level
        prefs = _load_json_dict(profile.preferences_json)
        prefs["wearer_style"] = style
        prefs["wearer_goal"] = goal
        prefs["wearer_boundary"] = boundary
        profile.preferences_json = json.dumps(prefs)
        profile.hard_limits_json = json.dumps(limits)
        reaction = _load_json_dict(profile.reaction_patterns_json)
        reaction["penalty_multiplier"] = penalty
        profile.reaction_patterns_json = json.dumps(reaction)
        needs = _load_json_dict(profile.needs_json)
        needs["gentle_mode"] = gentle
        profile.needs_json = json.dumps(needs)
    db.commit()
    return _render_profile_page(
        request=request,
        user=user,
        db=db,
        profile_message="Setup-Daten wurden aktualisiert.",
    )


@router.post("/profile/audio")
def save_audio_profile(
    request: Request,
    transcription_enabled: str = Form(default="false"),
    transcription_api_url: str = Form(default=""),
    transcription_api_key: str = Form(default=""),
    transcription_model: str = Form(default="whisper-1"),
    transcription_language: str = Form(default="de"),
    voice_realtime_enabled: str = Form(default="false"),
    voice_realtime_mode: str = Form(default="realtime-manual"),
    voice_realtime_agent_id: str = Form(default=""),
    voice_realtime_ws_url: str = Form(default="wss://api.x.ai/v1/realtime"),
    voice_realtime_api_key: str = Form(default=""),
    voice_realtime_default_voice: str = Form(default="Eve"),
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    settings.transcription_enabled = transcription_enabled.lower() in ("true", "on", "1", "enabled")
    settings.transcription_api_url = transcription_api_url.strip()[:500] or None
    if transcription_api_key.strip():
        settings.transcription_api_key = transcription_api_key.strip()[:4000]
    settings.transcription_model = transcription_model.strip()[:120] or "whisper-1"
    settings.transcription_language = transcription_language.strip()[:20] or None

    settings.voice_realtime_enabled = voice_realtime_enabled.lower() in ("true", "on", "1", "enabled")
    settings.voice_realtime_mode = "realtime-manual"
    settings.voice_realtime_agent_id = None
    settings.voice_realtime_ws_url = voice_realtime_ws_url.strip()[:500] or "wss://api.x.ai/v1/realtime"
    if voice_realtime_api_key.strip():
        settings.voice_realtime_api_key = voice_realtime_api_key.strip()[:4000]
    settings.voice_realtime_default_voice = voice_realtime_default_voice.strip()[:80] or "Eve"

    return _render_profile_page(
        request=request,
        user=user,
        db=db,
        llm_message="Audio-Gateway-Konfiguration gespeichert (laufende Instanz).",
    )


@router.post("/profile/audio/test")
async def test_audio_gateway(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    mode = (settings.voice_realtime_mode or "realtime-manual").strip().lower()
    if mode not in {"realtime-manual", "voice-agent"}:
        mode = "realtime-manual"

    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    api_key = (settings.voice_realtime_api_key or "").strip() or ((llm.api_key if llm else "") or "").strip()
    if not api_key:
        return JSONResponse({"ok": False, "error": "Kein Voice-API-Key gefunden (Audio und Sprache oder KI-Profil)."})

    if mode == "voice-agent" and not (settings.voice_realtime_agent_id or "").strip():
        return JSONResponse({"ok": False, "error": "Voice Agent ID fehlt (Mode A)."})

    payload = {"expires_after": {"seconds": 60}}
    if mode == "voice-agent":
        payload["voice_agent_id"] = settings.voice_realtime_agent_id

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                settings.voice_realtime_client_secret_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return JSONResponse(
            {
                "ok": False,
                "error": f"Voice Test fehlgeschlagen (HTTP {exc.response.status_code}).",
                "details": str(exc)[:200],
            }
        )
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Voice Test fehlgeschlagen: {str(exc)[:220]}"})

    has_secret = bool(
        data.get("client_secret")
        or data.get("value")
        or (isinstance(data.get("client_secret"), dict) and data["client_secret"].get("value"))
    )
    return JSONResponse(
        {
            "ok": has_secret,
            "mode": mode,
            "message": "Voice Gateway erreichbar." if has_secret else "Antwort erhalten, aber ohne client secret.",
        }
    )


@router.post("/profile/restart-setup")
def restart_setup(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    user.setup_completed = False

    profile = _resolve_default_player_profile(user, db, create_if_missing=False)
    if profile:
        profile.nickname = user.username
        profile.experience_level = "beginner"
        profile.preferences_json = json.dumps({})
        profile.hard_limits_json = json.dumps([])
        profile.reaction_patterns_json = json.dumps({"penalty_multiplier": 1.0})
        profile.needs_json = json.dumps({"gentle_mode": False})
    db.commit()
    return RedirectResponse(url="/experience", status_code=303)


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"title": f"{settings.app_name} History", "current_user": user},
    )


@router.get("/contracts", response_class=HTMLResponse)
def contracts_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(
        request=request,
        name="contracts.html",
        context={"title": f"{settings.app_name} Contracts", "current_user": user},
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
            "current_user": user,
            "session_id": session_id,
            "content_text": content_text,
            "signed_at": signed_at,
        },
    )


@router.get("/personas", response_class=HTMLResponse)
def personas_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(
        request=request,
        name="personas.html",
        context={"title": f"{settings.app_name} – Keyholder-Profile", "current_user": user},
    )


@router.get("/personas/partials/list", response_class=HTMLResponse)
def personas_list_partial(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    rows = db.query(Persona).order_by(Persona.id.asc()).all()
    items = list(rows)
    existing_names = {str(row.name).strip() for row in rows}
    for preset in PERSONA_PRESETS:
        if str(preset.get("name") or "").strip() in existing_names:
            continue
        system_persona = get_system_persona_by_key(str(preset.get("key") or ""))
        if system_persona:
            items.append(system_persona)
    return templates.TemplateResponse(
        request=request,
        name="partials/persona_list.html",
        context={
            "title": f"{settings.app_name} – Keyholder-Profile",
            "current_user": user,
            "items": items,
        },
    )


@router.get("/scenarios", response_class=HTMLResponse)
def scenarios_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(
        request=request,
        name="scenarios.html",
        context={"title": f"{settings.app_name} – Scenarios", "current_user": user},
    )


@router.get("/scenarios/partials/list", response_class=HTMLResponse)
def scenarios_list_partial(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    rows = db.query(Scenario).order_by(Scenario.id.asc()).all()
    items = []
    for row in rows:
        try:
            tags = json.loads(row.tags_json or "[]")
            if not isinstance(tags, list):
                tags = []
        except Exception:
            tags = []
        try:
            phases = json.loads(row.phases_json or "[]")
            if not isinstance(phases, list):
                phases = []
        except Exception:
            phases = []
        try:
            lorebook = json.loads(row.lorebook_json or "[]")
            if not isinstance(lorebook, list):
                lorebook = []
        except Exception:
            lorebook = []
        items.append({
            "id": row.id,
            "title": row.title,
            "summary": row.summary,
            "key": row.key,
            "tags": tags,
            "phases_count": len(phases),
            "lorebook_count": len(lorebook),
        })
    return templates.TemplateResponse(
        request=request,
        name="partials/scenario_list.html",
        context={
            "title": f"{settings.app_name} – Scenarios",
            "current_user": user,
            "items": items,
        },
    )


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={"title": f"{settings.app_name} – Inventory", "current_user": user},
    )


@router.get("/inventory/partials/list", response_class=HTMLResponse)
def inventory_list_partial(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    rows = (
        db.query(Item)
        .filter(Item.owner_user_id == user.id)
        .order_by(Item.name.asc())
        .all()
    )
    items = []
    for row in rows:
        try:
            tags = json.loads(row.tags_json or "[]")
            if not isinstance(tags, list):
                tags = []
        except Exception:
            tags = []
        items.append({
            "id": row.id,
            "key": row.key,
            "name": row.name,
            "category": row.category,
            "description": row.description,
            "tags": tags,
            "is_active": bool(row.is_active),
        })
    return templates.TemplateResponse(
        request=request,
        name="partials/inventory_list.html",
        context={
            "title": f"{settings.app_name} – Inventory",
            "current_user": user,
            "items": items,
        },
    )


@router.get("/api/settings/summary")
def settings_summary(
    request: Request,
    session_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(_build_settings_summary_payload(request=request, user=user, db=db, session_id=session_id))


@router.get("/profile/partials/session-summary", response_class=HTMLResponse)
def profile_session_summary_partial(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return HTMLResponse("<p class='hint'>Bitte zuerst anmelden.</p>", status_code=401)

    payload = _build_settings_summary_payload(request=request, user=user, db=db, session_id=None)
    session = payload.get("session")

    def _fmt_date(value: str | None) -> str:
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y, %H:%M:%S")
        except Exception:
            return str(value)

    def _fmt_secs(value: int | None) -> str:
        if value is None:
            return "—"
        total = max(0, int(value))
        d = total // 86400
        h = (total % 86400) // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{d}d {h}h {m}m {s}s"

    session_view = None
    if session:
        session_view = dict(session)
        session_view["lock_start_display"] = _fmt_date(session.get("lock_start"))
        session_view["lock_end_display"] = _fmt_date(session.get("lock_end"))
        session_view["remaining_display"] = _fmt_secs(session.get("remaining_seconds"))
        session_view["min_duration_display"] = _fmt_secs(session.get("min_duration_seconds"))
        session_view["max_duration_display"] = _fmt_secs(session.get("max_duration_seconds")) if session.get("max_duration_seconds") is not None else "—"
        session_view["task_penalty_display"] = _fmt_secs(session.get("task_penalty_total_seconds"))
        session_view["hygiene_penalty_display"] = _fmt_secs(session.get("hygiene_penalty_total_seconds"))
        session_view["hygiene_overrun_display"] = _fmt_secs(session.get("hygiene_overrun_total_seconds"))
        session_view["total_played_display"] = _fmt_secs(session.get("total_played_seconds"))
        session_view["last_opening_due_back_display"] = _fmt_date(session.get("last_opening_due_back_at")) if session.get("last_opening_due_back_at") else None

    return templates.TemplateResponse(
        request=request,
        name="partials/profile_session_summary.html",
        context={
            "request": request,
            "current_user": user,
            "session": session_view,
        },
    )


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


@router.post("/api/experience/draft")
def save_experience_draft(
    payload: ExperienceDraftRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    def _apply_contract_payload(target: dict) -> None:
        contract = _contract_preferences_from_prefs(target)
        mapping = {
            "keyholder_title": payload.contract_keyholder_title,
            "wearer_title": payload.contract_wearer_title,
            "goal": payload.contract_goal,
            "method": payload.contract_method,
            "wearing_schedule": payload.contract_wearing_schedule,
            "touch_rules": payload.contract_touch_rules,
            "orgasm_rules": payload.contract_orgasm_rules,
            "reward_policy": payload.contract_reward_policy,
            "termination_policy": payload.contract_termination_policy,
        }
        for key, value in mapping.items():
            if value is None:
                continue
            contract[key] = str(value).strip()[:4000]
        target["contract"] = normalize_contract_preferences(contract)

    default_profile = _resolve_default_player_profile(user, db, create_if_missing=False)
    if default_profile:
        prefs = _load_json_dict(default_profile.preferences_json)
        reaction = _load_json_dict(default_profile.reaction_patterns_json)
        needs = _load_json_dict(default_profile.needs_json)
        _apply_contract_payload(prefs)
        if payload.wearer_nickname is not None:
            default_profile.nickname = payload.wearer_nickname.strip()[:80] or default_profile.nickname
        if payload.experience_level is not None:
            level_value = payload.experience_level.strip()
            if level_value in ("beginner", "intermediate", "advanced"):
                default_profile.experience_level = level_value
        if payload.persona_tone is not None:
            prefs["wearer_style"] = payload.persona_tone.strip()[:80] or None
        if payload.scenario_preset is not None:
            prefs["wearer_goal"] = payload.scenario_preset.strip()[:120] or None
        if payload.hard_limits is not None:
            prefs["wearer_boundary"] = payload.hard_limits.strip()[:1500] or None
            limits = [part.strip() for part in payload.hard_limits.split(",") if part.strip()]
            default_profile.hard_limits_json = json.dumps(limits)
        if payload.penalty_multiplier is not None:
            reaction["penalty_multiplier"] = max(0.1, min(5.0, float(payload.penalty_multiplier)))
        if payload.default_penalty_seconds is not None:
            reaction["default_penalty_seconds"] = int(payload.default_penalty_seconds)
        if payload.max_penalty_seconds is not None:
            reaction["max_penalty_seconds"] = int(payload.max_penalty_seconds)
        if payload.gentle_mode is not None:
            needs["gentle_mode"] = bool(payload.gentle_mode)
        if payload.hygiene_opening_max_duration_seconds is not None:
            prefs["hygiene_opening_max_duration_seconds"] = int(payload.hygiene_opening_max_duration_seconds)
        default_profile.preferences_json = json.dumps(prefs)
        default_profile.reaction_patterns_json = json.dumps(reaction)
        default_profile.needs_json = json.dumps(needs)

    active_session = None
    active_player = None
    active_persona = None
    if user.active_session_id:
        active_session = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()
        if active_session:
            active_player = db.query(PlayerProfile).filter(PlayerProfile.id == active_session.player_profile_id).first()
            active_persona = db.query(Persona).filter(Persona.id == active_session.persona_id).first()

    if payload.persona_name is not None and active_session:
        requested_name = payload.persona_name.strip()[:120]
        target_persona = None
        if requested_name:
            target_persona = db.query(Persona).filter(Persona.name == requested_name).first()
            if not target_persona and active_persona:
                active_persona.name = requested_name
                target_persona = active_persona
            if not target_persona:
                target_persona = Persona(name=requested_name)
                db.add(target_persona)
                db.flush()
        if target_persona:
            active_session.persona_id = target_persona.id
            active_persona = target_persona

    if active_persona:
        if payload.persona_tone is not None:
            active_persona.speech_style_tone = payload.persona_tone.strip()[:60] or None
        if payload.persona_dominance is not None:
            dominance = payload.persona_dominance.strip()[:60] or None
            active_persona.speech_style_dominance = dominance
        if payload.persona_description is not None:
            active_persona.description = payload.persona_description.strip()[:4000] or None
        if payload.persona_system_prompt is not None:
            active_persona.system_prompt = payload.persona_system_prompt.strip()[:4000] or None

    if active_player:
        prefs: dict = {}
        reaction: dict = {}
        needs: dict = {}
        try:
            parsed = json.loads(active_player.preferences_json or "{}")
            if isinstance(parsed, dict):
                prefs = parsed
        except Exception:
            prefs = {}
        try:
            parsed = json.loads(active_player.reaction_patterns_json or "{}")
            if isinstance(parsed, dict):
                reaction = parsed
        except Exception:
            reaction = {}
        try:
            parsed = json.loads(active_player.needs_json or "{}")
            if isinstance(parsed, dict):
                needs = parsed
        except Exception:
            needs = {}
        _apply_contract_payload(prefs)

        if payload.wearer_nickname is not None:
            active_player.nickname = payload.wearer_nickname.strip()[:80] or active_player.nickname
        if payload.experience_level is not None:
            level_value = payload.experience_level.strip()
            active_player.experience_level = (
                level_value if level_value in ("beginner", "intermediate", "advanced") else active_player.experience_level
            )
        if payload.hard_limits is not None:
            limits = [part.strip() for part in payload.hard_limits.split(",") if part.strip()]
            active_player.hard_limits_json = json.dumps(limits)
        if payload.penalty_multiplier is not None:
            reaction["penalty_multiplier"] = max(0.1, min(5.0, float(payload.penalty_multiplier)))
        if payload.default_penalty_seconds is not None:
            reaction["default_penalty_seconds"] = int(payload.default_penalty_seconds)
        if payload.max_penalty_seconds is not None:
            reaction["max_penalty_seconds"] = int(payload.max_penalty_seconds)
        if payload.gentle_mode is not None:
            needs["gentle_mode"] = bool(payload.gentle_mode)
        if payload.scenario_preset is not None:
            prefs["scenario_preset"] = payload.scenario_preset.strip()[:120] or None
        if payload.hygiene_opening_max_duration_seconds is not None:
            prefs["hygiene_opening_max_duration_seconds"] = int(payload.hygiene_opening_max_duration_seconds)
        active_player.preferences_json = json.dumps(prefs)
        active_player.reaction_patterns_json = json.dumps(reaction)
        active_player.needs_json = json.dumps(needs)

    if active_session:
        if payload.min_duration_seconds is not None:
            active_session.min_duration_seconds = int(payload.min_duration_seconds)
        if payload.no_max_limit:
            active_session.max_duration_seconds = None
        elif payload.max_duration_seconds is not None:
            active_session.max_duration_seconds = int(payload.max_duration_seconds)
        if payload.hygiene_limit_daily is not None:
            active_session.hygiene_limit_daily = int(payload.hygiene_limit_daily)
        if payload.hygiene_limit_weekly is not None:
            active_session.hygiene_limit_weekly = int(payload.hygiene_limit_weekly)
        if payload.hygiene_limit_monthly is not None:
            active_session.hygiene_limit_monthly = int(payload.hygiene_limit_monthly)
        if payload.hygiene_opening_max_duration_seconds is not None:
            active_session.hygiene_opening_max_duration_seconds = int(payload.hygiene_opening_max_duration_seconds)
        if payload.llm_provider is not None:
            active_session.llm_provider = payload.llm_provider.strip()[:50] or None
        if payload.llm_api_url is not None:
            active_session.llm_api_url = payload.llm_api_url.strip()[:500] or None
        if payload.llm_api_key:
            active_session.llm_api_key = payload.llm_api_key.strip()[:4000]
        if payload.llm_chat_model is not None:
            active_session.llm_chat_model = payload.llm_chat_model.strip()[:120] or None
        if payload.llm_vision_model is not None:
            active_session.llm_vision_model = payload.llm_vision_model.strip()[:120] or None
        if payload.llm_active is not None:
            active_session.llm_profile_active = bool(payload.llm_active)

        if payload.seal_enabled and payload.initial_seal_number:
            next_seal = payload.initial_seal_number.strip()[:120]
            if next_seal:
                active_seal = (
                    db.query(SealHistory)
                    .filter(SealHistory.session_id == active_session.id, SealHistory.status == "active")
                    .order_by(SealHistory.applied_at.desc())
                    .first()
                )
                if active_seal:
                    active_seal.seal_number = next_seal
                else:
                    db.add(
                        SealHistory(
                            session_id=active_session.id,
                            seal_number=next_seal,
                            status="active",
                            note="Updated via experience draft",
                        )
                    )

    llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if not llm:
        llm = LlmProfile(profile_key="default")
        db.add(llm)

    if payload.llm_provider is not None:
        llm.provider = payload.llm_provider.strip()[:50] or "stub"
    if payload.llm_api_url is not None:
        llm.api_url = payload.llm_api_url.strip()[:500] or None
    if payload.llm_api_key:
        llm.api_key = payload.llm_api_key.strip()[:4000]
    if payload.llm_chat_model is not None:
        llm.chat_model = payload.llm_chat_model.strip()[:120] or None
    if payload.llm_vision_model is not None:
        llm.vision_model = payload.llm_vision_model.strip()[:120] or None
    if payload.llm_active is not None:
        llm.profile_active = bool(payload.llm_active)

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
            "lovense_status": lovense_status_payload(),
            "play_js_version": _asset_version("js/play.js"),
            "play_css_version": _asset_version("css/play.css"),
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    target_session = None
    if user.active_session_id:
        target_session = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()
    if target_session is None:
        target_session = db.query(SessionModel).order_by(SessionModel.id.desc()).first()
    if target_session is None:
        return RedirectResponse(url="/experience", status_code=303)
    return RedirectResponse(url=f"/dashboard/{target_session.id}", status_code=303)


@router.get("/dashboard/{session_id}", response_class=HTMLResponse)
def dashboard_page(session_id: int, request: Request, db: Session = Depends(get_db)):
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
        name="dashboard.html",
        context={
            "title": f"Dashboard – {settings.app_name}",
            "current_user": user,
            "session_id": session_id,
            "session_status": session_obj.status,
            "ws_token": session_obj.ws_auth_token or "",
            "persona_id": persona.id if persona else None,
            "persona_missing": persona is None,
            "persona_name": persona.name if persona else "Keyholderin",
            "player_nickname": player.nickname if player else user.username,
            "lock_end": session_obj.lock_end.isoformat() if session_obj.lock_end else None,
            "dashboard_css_version": _asset_version("css/dashboard.css"),
            "dashboard_js_version": _asset_version("js/dashboard.js"),
            "lovense_status": lovense_status_payload(),
        },
    )


@router.get("/toys", response_class=HTMLResponse)
def toys_redirect(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    target_session = None
    if user.active_session_id:
        target_session = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()
    if target_session is None:
        target_session = db.query(SessionModel).order_by(SessionModel.id.desc()).first()
    if target_session is None:
        return RedirectResponse(url="/experience", status_code=303)
    return RedirectResponse(url=f"/toys/{target_session.id}", status_code=303)


@router.get("/toys/{session_id}", response_class=HTMLResponse)
def toys_page(session_id: int, request: Request, db: Session = Depends(get_db)):
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
        name="toys.html",
        context={
            "title": f"Toys – {settings.app_name}",
            "current_user": user,
            "session_id": session_id,
            "session_status": session_obj.status,
            "ws_token": session_obj.ws_auth_token or "",
            "persona_name": persona.name if persona else "Keyholderin",
            "player_nickname": player.nickname if player else user.username,
            "lock_end": session_obj.lock_end.isoformat() if session_obj.lock_end else None,
            "dashboard_css_version": _asset_version("css/dashboard.css"),
            "toys_js_version": _asset_version("js/toys.js"),
            "lovense_status": lovense_status_payload(),
        },
    )


@router.get("/game/{session_id}", response_class=HTMLResponse)
def game_page(
    session_id: int,
    request: Request,
    module_key: str = Query(default="posture_training", max_length=120),
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session_obj is None:
        return RedirectResponse(url="/experience", status_code=303)

    module = get_module(module_key)
    if module is None:
        return RedirectResponse(url="/games", status_code=303)

    latest_run = (
        db.query(GameRun)
        .filter(GameRun.session_id == session_id, GameRun.module_key == module_key)
        .order_by(GameRun.id.desc())
        .first()
    )

    initial_setup = {
        "duration_minutes": 20,
        "transition_seconds": 0 if module.key in {"dont_move", "tiptoeing"} else 8,
        "difficulty": "medium",
        "max_misses_before_penalty": 3,
        "session_penalty_days": 0,
        "session_penalty_hours": 0,
        "session_penalty_minutes": 5,
    }
    if latest_run is not None:
        base_duration_seconds = max(60, int(latest_run.total_duration_seconds or 0) - int(latest_run.retry_extension_seconds or 0))
        penalty_total = max(0, int(latest_run.session_penalty_seconds or 0))
        raw_transition = int(latest_run.transition_seconds or 0)
        default_transition = 0 if module.key in {"dont_move", "tiptoeing"} else 8
        initial_setup = {
            "duration_minutes": max(1, int(round(base_duration_seconds / 60))),
            "transition_seconds": max(0, min(60, raw_transition if raw_transition > 0 else default_transition)),
            "difficulty": latest_run.difficulty_key or "medium",
            "max_misses_before_penalty": max(1, int(latest_run.max_misses_before_penalty or 3)),
            "session_penalty_days": penalty_total // 86400,
            "session_penalty_hours": (penalty_total % 86400) // 3600,
            "session_penalty_minutes": (penalty_total % 3600) // 60,
        }

    return templates.TemplateResponse(
        request=request,
        name="game_posture.html",
        context={
            "title": f"Game Mode - {settings.app_name}",
            "current_user": user,
            "session_id": session_id,
            "module_key": module.key,
            "module_title": module.title,
            "module_summary": module.summary,
            "latest_run_id": latest_run.id if latest_run else None,
            "initial_setup": initial_setup,
        },
    )


@router.get("/games", response_class=HTMLResponse)
def games_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    current_session = None
    if user.active_session_id:
        current_session = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()
    if current_session is None:
        current_session = db.query(SessionModel).order_by(SessionModel.id.desc()).first()

    current_session_payload = None
    if current_session is not None:
        persona = db.query(Persona).filter(Persona.id == current_session.persona_id).first()
        player = db.query(PlayerProfile).filter(PlayerProfile.id == current_session.player_profile_id).first()
        current_session_payload = {
            "id": current_session.id,
            "status": current_session.status,
            "persona_name": persona.name if persona else "-",
            "player_nickname": player.nickname if player else "-",
        }

    modules = [as_public_module_payload(module) for module in list_modules()]

    configured_counts = {
        module_key: int(count)
        for module_key, count in db.query(
            GamePostureTemplate.module_key,
            func.count(GamePostureTemplate.id),
        )
        .filter(GamePostureTemplate.is_active == True)  # noqa: E712
        .group_by(GamePostureTemplate.module_key)
        .all()
    }

    for module in modules:
        configured = int(configured_counts.get(module["key"], 0))
        module["configured_steps_count"] = configured
        module["uses_custom_steps"] = configured > 0

    return templates.TemplateResponse(
        request=request,
        name="games.html",
        context={
            "title": f"{settings.app_name} - Games",
            "current_user": user,
            "modules": modules,
            "current_session": current_session_payload,
        },
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    modules = [as_public_module_payload(module) for module in list_modules()]

    current_session = None
    if user.active_session_id:
        current_session = db.query(SessionModel).filter(SessionModel.id == user.active_session_id).first()

    counts = {
        "personas": int(db.query(func.count(Persona.id)).scalar() or 0),
        "scenarios": int(db.query(func.count(Scenario.id)).scalar() or 0),
        "inventory_items": int(db.query(func.count(Item.id)).scalar() or 0),
        "postures": int(db.query(func.count(GamePostureTemplate.id)).scalar() or 0),
        "game_modules": len(modules),
        "game_runs": int(db.query(func.count(GameRun.id)).scalar() or 0),
        "active_sessions": int(db.query(func.count(SessionModel.id)).filter(SessionModel.status == "active").scalar() or 0),
    }

    admin_sections = [
        {
            "title": "Personas",
            "summary": "Charaktere, Sprachstil und Verhalten zentral pflegen.",
            "href": "/personas",
            "count": counts["personas"],
            "count_label": "Eintraege",
        },
        {
            "title": "Scenarios",
            "summary": "Szenarien, Phasen und Lorebook-Inhalte verwalten.",
            "href": "/scenarios",
            "count": counts["scenarios"],
            "count_label": "Eintraege",
        },
        {
            "title": "Inventar",
            "summary": "Items, Kategorien und Verfuegbarkeit steuern.",
            "href": "/inventory",
            "count": counts["inventory_items"],
            "count_label": "Items",
        },
        {
            "title": "Games",
            "summary": "Spielmodule, Konfigurationen und Run-Flow ueberblicken.",
            "href": "/games",
            "secondary_href": "/games/module-settings?module_key=dont_move",
            "secondary_label": "Spiele Konfiguration",
            "count": counts["game_modules"],
            "count_label": "Module",
        },
        {
            "title": "Posture Library",
            "summary": "Gemeinsamer Pool fuer alle Spiele inkl. Modul-Freigaben.",
            "href": "/games/postures?module_key=posture_training",
            "secondary_href": "/admin/postures/matrix",
            "secondary_label": "Matrix",
            "count": counts["postures"],
            "count_label": "Postures",
        },
        {
            "title": "Vertraege & Historie",
            "summary": "Vertragsansicht, Addenda und Session-Historie.",
            "href": "/contracts",
            "secondary_href": "/history",
            "secondary_label": "Historie",
            "count": counts["active_sessions"],
            "count_label": "Aktive Sessions",
        },
        {
            "title": "Operations",
            "summary": "Wartung und operative Uebersicht.",
            "href": "/admin/operations",
            "count": counts["game_runs"],
            "count_label": "Runs",
        },
    ]

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "title": f"{settings.app_name} - Admin",
            "current_user": user,
            "sections": admin_sections,
            "counts": counts,
            "current_session": current_session,
        },
    )


@router.get("/admin/postures/matrix", response_class=HTMLResponse)
def admin_posture_matrix_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        request=request,
        name="admin_posture_matrix.html",
        context={
            "title": f"{settings.app_name} - Posture Matrix",
            "current_user": user,
        },
    )


@router.get("/admin/operations", response_class=HTMLResponse)
def admin_operations_page(request: Request, db: Session = Depends(get_db)):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    counts = {
        "active_sessions": int(db.query(func.count(SessionModel.id)).filter(SessionModel.status == "active").scalar() or 0),
        "game_runs": int(db.query(func.count(GameRun.id)).scalar() or 0),
        "contracts": int(db.query(func.count(Contract.id)).scalar() or 0),
    }

    return templates.TemplateResponse(
        request=request,
        name="admin_operations.html",
        context={
            "title": f"{settings.app_name} - Operations",
            "current_user": user,
            "counts": counts,
        },
    )


@router.get("/games/postures", response_class=HTMLResponse)
def games_postures_page(
    request: Request,
    module_key: str = Query(default="posture_training", max_length=120),
    db: Session = Depends(get_db),
):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    module = get_module(module_key)
    if module is None:
        return RedirectResponse(url="/games", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="game_posture_manage.html",
        context={
            "title": f"{settings.app_name} - Postures",
            "current_user": user,
            "module_key": module.key,
            "module_title": module.title,
            "module_summary": module.summary,
        },
    )


@router.get("/games/module-settings", response_class=HTMLResponse)
def games_module_settings_page(
    request: Request,
    module_key: str = Query(default="dont_move", max_length=120),
    db: Session = Depends(get_db),
):
    user = _require_admin_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    module = get_module(module_key)
    if module is None:
        return RedirectResponse(url="/games", status_code=303)

    modules = [as_public_module_payload(item) for item in list_modules()]

    return templates.TemplateResponse(
        request=request,
        name="game_module_settings.html",
        context={
            "title": f"{settings.app_name} - Spiel-Presets",
            "current_user": user,
            "module_key": module.key,
            "module_title": module.title,
            "module_summary": module.summary,
            "modules": modules,
        },
    )


@router.get("/experience", response_class=HTMLResponse)
def experience_page(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if user is None:
        return RedirectResponse(url="/", status_code=303)
    target = _redirect_if_active_session(user, db)
    if target:
        return RedirectResponse(url=target, status_code=303)

    default_profile = _resolve_default_player_profile(user, db, create_if_missing=True)
    setup_ctx = _setup_context_from_user_and_profile(user, default_profile)
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="experience.html",
        context={"title": f"{settings.app_name} Chat", "current_user": user, "setup": setup_ctx},
    )
