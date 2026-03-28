import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.contract import Contract, ContractAddendum
from app.models.hygiene_opening import HygieneOpening
from app.models.llm_profile import LlmProfile
from app.models.media_asset import MediaAsset
from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.safety_log import SafetyLog
from app.models.scenario import Scenario
from app.models.seal_history import SealHistory
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.models.verification import Verification
from app.services.contract_service import build_contract_context, build_contract_text, normalize_contract_preferences
from app.services.pdf_export import build_simple_text_pdf
from app.services.relationship_memory import build_relationship_memory
from app.services.roleplay_state import build_roleplay_state, initialize_roleplay_state, serialize_roleplay_state
from app.services.session_service import SessionService
from app.services.audit_logger import audit_log
from app.services.behavior_profile import behavior_profile_from_entities, behavior_profile_from_scenario_key
from app.services.session_access import bind_session_profile_to_user, get_accessible_session, get_current_session_user, get_owned_session
from app.security import require_admin_session_user, verify_admin_secret

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _resolve_active_scenario_phase(db: Session, scenario_key: str | None, preferred_phase_id: str | None = None) -> dict | None:
    key = str(scenario_key or "").strip()
    if not key:
        return None

    phases: list[dict] = []
    db_scenario = db.query(Scenario).filter(Scenario.key == key).first()
    if db_scenario:
        try:
            parsed = json.loads(db_scenario.phases_json or "[]")
            if isinstance(parsed, list):
                phases = [item for item in parsed if isinstance(item, dict)]
        except Exception:
            phases = []
    else:
        from app.routers.scenarios import SCENARIO_PRESETS

        preset = next((item for item in SCENARIO_PRESETS if str(item.get("key") or "").strip() == key), None)
        raw_phases = preset.get("phases", []) if isinstance(preset, dict) else []
        if isinstance(raw_phases, list):
            phases = [item for item in raw_phases if isinstance(item, dict)]

    if not phases:
        return None

    phase_id = str(preferred_phase_id or "").strip()
    if phase_id:
        matched = next((phase for phase in phases if str(phase.get("phase_id") or "").strip() == phase_id), None)
        if matched is not None:
            return matched
    return phases[0]


class CreateSessionRequest(BaseModel):
    persona_name: str | None = Field(default=None, min_length=1, max_length=120)
    player_nickname: str | None = Field(default=None, min_length=1, max_length=120)
    min_duration_seconds: int | None = Field(default=None, ge=60)
    max_duration_seconds: int | None = Field(default=None, ge=60)
    hygiene_limit_daily: int | None = Field(default=None, ge=0)
    hygiene_limit_weekly: int | None = Field(default=None, ge=0)
    hygiene_limit_monthly: int | None = Field(default=None, ge=0)
    hygiene_opening_max_duration_seconds: int | None = Field(default=None, ge=60)
    experience_level: str | None = Field(default=None, max_length=50)
    wearer_style: str | None = Field(default=None, max_length=80)
    wearer_goal: str | None = Field(default=None, max_length=120)
    wearer_boundary: str | None = Field(default=None, max_length=1500)
    hard_limits: list[str] | None = None
    scenario_preset: str | None = Field(default=None, max_length=120)
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
    template_session_id: int | None = Field(default=None, ge=1)
    llm_provider: str | None = Field(default=None, max_length=50)
    llm_api_url: str | None = Field(default=None, max_length=500)
    llm_api_key: str | None = Field(default=None, max_length=4000)
    llm_chat_model: str | None = Field(default=None, max_length=120)
    llm_vision_model: str | None = Field(default=None, max_length=120)
    llm_active: bool | None = Field(default=None)


class ProposeAddendumRequest(BaseModel):
    change_description: str = Field(min_length=3)
    proposed_changes: dict = Field(default_factory=dict)


class AddendumConsentRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


class TimerAdjustRequest(BaseModel):
    seconds: int = Field(ge=1)


class UpdatePlayerProfileRequest(BaseModel):
    experience_level: str | None = Field(default=None, min_length=1, max_length=50)
    preferences: dict | None = None
    soft_limits: list[str] | None = None
    hard_limits: list[str] | None = None
    reaction_patterns: dict | None = None
    needs: dict | None = None
    avatar_media_id: int | None = Field(default=None, ge=1)
    clear_avatar: bool | None = None


class UpdateSessionPersonaRequest(BaseModel):
    persona_id: int = Field(ge=1)


def _resolve_persona_for_session(payload: CreateSessionRequest, db: Session, current_persona: Persona | None) -> Persona:
    requested_name = str(payload.persona_name or "").strip()
    if not requested_name:
        raise RequestValidationError(errors=[{"type": "missing", "loc": ("body", "persona_name"), "msg": "Field required", "input": None}])
    existing = db.query(Persona).filter(Persona.name == requested_name).first()
    if existing:
        return existing
    if current_persona and current_persona.name:
        current_persona.name = requested_name
        db.add(current_persona)
        db.flush()
        return current_persona
    persona = Persona(name=requested_name)
    db.add(persona)
    db.flush()
    return persona


ADDENDUM_SUPPORTED_FIELDS: dict[str, dict[str, str]] = {
    "min_duration_seconds": {"label": "Mindestdauer", "category": "contract", "effect_scope": "contract_bounds"},
    "max_duration_seconds": {"label": "Maximaldauer", "category": "contract", "effect_scope": "contract_bounds"},
    "hygiene_limit_daily": {"label": "Hygiene Tageslimit", "category": "policy", "effect_scope": "active_session_policy"},
    "hygiene_limit_weekly": {"label": "Hygiene Wochenlimit", "category": "policy", "effect_scope": "active_session_policy"},
    "hygiene_limit_monthly": {"label": "Hygiene Monatslimit", "category": "policy", "effect_scope": "active_session_policy"},
    "hygiene_opening_max_duration_seconds": {"label": "Maximale Hygiene-Oeffnungsdauer", "category": "policy", "effect_scope": "active_session_policy"},
    "penalty_multiplier": {"label": "Penalty-Multiplikator", "category": "policy", "effect_scope": "active_session_policy"},
    "default_penalty_seconds": {"label": "Standardstrafe", "category": "policy", "effect_scope": "active_session_policy"},
    "max_penalty_seconds": {"label": "Maximalstrafe", "category": "policy", "effect_scope": "active_session_policy"},
    "active_rules_add": {"label": "Aktive Regeln hinzufuegen", "category": "protocol", "effect_scope": "roleplay_protocol"},
    "active_rules_remove": {"label": "Aktive Regeln entfernen", "category": "protocol", "effect_scope": "roleplay_protocol"},
    "open_orders_add": {"label": "Offene Anweisungen hinzufuegen", "category": "protocol", "effect_scope": "roleplay_protocol"},
    "open_orders_remove": {"label": "Offene Anweisungen entfernen", "category": "protocol", "effect_scope": "roleplay_protocol"},
}

ADDENDUM_SESSION_INT_FIELDS = {
    "min_duration_seconds",
    "max_duration_seconds",
    "hygiene_limit_daily",
    "hygiene_limit_weekly",
    "hygiene_limit_monthly",
    "hygiene_opening_max_duration_seconds",
}

ADDENDUM_REACTION_FIELDS = {
    "penalty_multiplier",
    "default_penalty_seconds",
    "max_penalty_seconds",
}

ADDENDUM_PROTOCOL_LIST_FIELDS = {
    "active_rules_add",
    "active_rules_remove",
    "open_orders_add",
    "open_orders_remove",
}


def _ensure_avatar_exists(db: Session, avatar_media_id: int | None) -> None:
    if avatar_media_id is None:
        return
    asset = db.query(MediaAsset).filter(MediaAsset.id == avatar_media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Avatar media not found")
    if asset.media_kind != "avatar":
        raise HTTPException(status_code=409, detail="Media asset is not an avatar")


def _ensure_ws_auth_token(session_obj: SessionModel) -> None:
    if session_obj.ws_auth_token:
        return
    session_obj.ws_auth_token = secrets.token_urlsafe(24)
    session_obj.ws_auth_token_created_at = datetime.now(timezone.utc)


def _rotate_ws_auth_token(session_obj: SessionModel) -> None:
    session_obj.ws_auth_token = secrets.token_urlsafe(24)
    session_obj.ws_auth_token_created_at = datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _remaining_seconds(session_obj: SessionModel, now: datetime) -> int:
    if session_obj.lock_end is None:
        return 0
    anchor = now
    if session_obj.timer_frozen and session_obj.freeze_start is not None:
        anchor = _as_utc(session_obj.freeze_start)
    return max(0, int((_as_utc(session_obj.lock_end) - anchor).total_seconds()))


def _load_json_dict(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_text_items(value: object, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail="Addendum list fields must be arrays of text")
    items: list[str] = []
    seen: set[str] = set()
    for raw in value:
        text = str(raw or "").strip()
        if not text:
            continue
        text = text[:160]
        lowered = text.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _normalize_addendum_changes(
    proposed_changes: dict,
    *,
    session_obj: SessionModel,
) -> dict:
    if not isinstance(proposed_changes, dict) or not proposed_changes:
        raise HTTPException(status_code=400, detail="Addendum must include proposed_changes")

    normalized: dict[str, object] = {}
    unsupported = sorted(set(str(key) for key in proposed_changes.keys()) - set(ADDENDUM_SUPPORTED_FIELDS.keys()))
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported addendum fields: {', '.join(unsupported)}",
        )

    for key, value in proposed_changes.items():
        if key in ADDENDUM_SESSION_INT_FIELDS:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{key} must be an integer")
            minimum = 60 if "duration_seconds" in key else 0
            if parsed < minimum:
                raise HTTPException(status_code=400, detail=f"{key} must be >= {minimum}")
            normalized[key] = parsed
            continue

        if key == "penalty_multiplier":
            try:
                parsed_multiplier = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="penalty_multiplier must be numeric")
            normalized[key] = max(0.1, min(5.0, round(parsed_multiplier, 2)))
            continue

        if key in {"default_penalty_seconds", "max_penalty_seconds"}:
            try:
                parsed_penalty = int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{key} must be an integer")
            if parsed_penalty < 0:
                raise HTTPException(status_code=400, detail=f"{key} must be >= 0")
            normalized[key] = parsed_penalty
            continue

        if key in ADDENDUM_PROTOCOL_LIST_FIELDS:
            normalized_list = _normalize_text_items(value)
            if not normalized_list:
                raise HTTPException(status_code=400, detail=f"{key} must contain at least one entry")
            normalized[key] = normalized_list
            continue

    effective_min = int(normalized.get("min_duration_seconds", session_obj.min_duration_seconds))
    effective_max = normalized.get("max_duration_seconds", session_obj.max_duration_seconds)
    if effective_max is not None and int(effective_max) < effective_min:
        raise HTTPException(status_code=400, detail="max_duration_seconds must be >= min_duration_seconds")

    max_penalty = normalized.get("max_penalty_seconds")
    default_penalty = normalized.get("default_penalty_seconds")
    if max_penalty is not None and default_penalty is not None and int(max_penalty) < int(default_penalty):
        raise HTTPException(status_code=400, detail="max_penalty_seconds must be >= default_penalty_seconds")

    return normalized


def _compute_addendum_consent_tier(
    normalized_changes: dict,
    *,
    session_obj: SessionModel,
    profile: PlayerProfile | None,
) -> str:
    reaction = _load_json_dict(profile.reaction_patterns_json if profile else "{}")

    min_before = int(session_obj.min_duration_seconds or 0)
    max_before = int(session_obj.max_duration_seconds or 0) if session_obj.max_duration_seconds is not None else None
    if "min_duration_seconds" in normalized_changes and int(normalized_changes["min_duration_seconds"]) - min_before >= 86400:
        return "high_impact"
    if "max_duration_seconds" in normalized_changes and max_before is not None and max_before - int(normalized_changes["max_duration_seconds"]) >= 86400:
        return "high_impact"

    for key in ("hygiene_limit_daily", "hygiene_limit_weekly", "hygiene_limit_monthly"):
        if key in normalized_changes:
            before = getattr(session_obj, key)
            after = int(normalized_changes[key])
            if before is not None and after < int(before):
                return "high_impact"

    if "hygiene_opening_max_duration_seconds" in normalized_changes:
        before_opening = session_obj.hygiene_opening_max_duration_seconds
        after_opening = int(normalized_changes["hygiene_opening_max_duration_seconds"])
        if before_opening is not None and after_opening < int(before_opening):
            return "high_impact"

    if "penalty_multiplier" in normalized_changes:
        before_multiplier = float(reaction.get("penalty_multiplier", 1.0) or 1.0)
        if float(normalized_changes["penalty_multiplier"]) - before_multiplier >= 0.5:
            return "high_impact"

    for penalty_key in ("default_penalty_seconds", "max_penalty_seconds"):
        if penalty_key in normalized_changes:
            before_penalty = int(reaction.get(penalty_key, 0) or 0)
            if int(normalized_changes[penalty_key]) - before_penalty >= 3600:
                return "high_impact"

    return "standard"


def _build_addendum_metadata(
    normalized_changes: dict,
    *,
    session_obj: SessionModel,
    profile: PlayerProfile | None,
) -> dict:
    scopes: list[str] = []
    labels: list[str] = []
    for key in normalized_changes.keys():
        meta = ADDENDUM_SUPPORTED_FIELDS.get(key, {})
        scope = meta.get("effect_scope")
        label = meta.get("label")
        if scope and scope not in scopes:
            scopes.append(scope)
        if label:
            labels.append(label)
    scope_descriptions = {
        "contract_bounds": "Vertragsrahmen",
        "active_session_policy": "Aktive Session-Policy",
        "roleplay_protocol": "Roleplay-Protokoll",
    }
    return {
        "validated_changes": normalized_changes,
        "consent_tier": _compute_addendum_consent_tier(normalized_changes, session_obj=session_obj, profile=profile),
        "effect_scopes": scopes,
        "effect_summary": ", ".join(scope_descriptions[item] for item in scopes) if scopes else "Keine Wirkung",
        "supported_fields": ADDENDUM_SUPPORTED_FIELDS,
        "field_labels": labels,
    }


def _addendum_payload(
    item: ContractAddendum,
    *,
    session_obj: SessionModel,
    profile: PlayerProfile | None,
) -> dict:
    proposed_changes = _load_json_dict(item.proposed_changes_json)
    metadata = _build_addendum_metadata(proposed_changes, session_obj=session_obj, profile=profile)
    return {
        "id": item.id,
        "change_description": item.change_description,
        "proposed_changes": proposed_changes,
        "proposed_by": item.proposed_by,
        "player_consent": item.player_consent,
        "player_consent_at": str(item.player_consent_at) if item.player_consent_at else None,
        "created_at": str(item.created_at),
        **metadata,
    }


def _apply_protocol_addendum(db: Session, session_obj: SessionModel, proposed_changes: dict) -> list[str]:
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first() if session_obj.player_profile_id else None
    prefs = _load_json_dict(profile.preferences_json if profile else None)
    roleplay_state = build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=prefs.get("scenario_preset"),
        active_phase=_resolve_active_scenario_phase(db, prefs.get("scenario_preset"), prefs.get("scenario_phase_id")),
    )
    protocol = dict(roleplay_state["protocol"])
    active_rules = list(protocol.get("active_rules") or [])
    open_orders = list(protocol.get("open_orders") or [])
    applied_notes: list[str] = []

    if "active_rules_add" in proposed_changes:
        additions = [item for item in proposed_changes["active_rules_add"] if item not in active_rules]
        if additions:
            active_rules.extend(additions)
            applied_notes.append(f"Aktive Regeln +{len(additions)}")
    if "active_rules_remove" in proposed_changes:
        removals = {item for item in proposed_changes["active_rules_remove"]}
        next_rules = [item for item in active_rules if item not in removals]
        if len(next_rules) != len(active_rules):
            applied_notes.append(f"Aktive Regeln -{len(active_rules) - len(next_rules)}")
            active_rules = next_rules

    if "open_orders_add" in proposed_changes:
        additions = [item for item in proposed_changes["open_orders_add"] if item not in open_orders]
        if additions:
            open_orders.extend(additions)
            applied_notes.append(f"Offene Anweisungen +{len(additions)}")
    if "open_orders_remove" in proposed_changes:
        removals = {item for item in proposed_changes["open_orders_remove"]}
        next_orders = [item for item in open_orders if item not in removals]
        if len(next_orders) != len(open_orders):
            applied_notes.append(f"Offene Anweisungen -{len(open_orders) - len(next_orders)}")
            open_orders = next_orders

    protocol["active_rules"] = active_rules
    protocol["open_orders"] = open_orders
    roleplay_state["protocol"] = protocol
    serialized = serialize_roleplay_state(roleplay_state)
    session_obj.relationship_state_json = serialized["relationship_state_json"]
    session_obj.protocol_state_json = serialized["protocol_state_json"]
    session_obj.scene_state_json = serialized["scene_state_json"]
    return applied_notes


def _session_blueprint(db: Session, session_obj: SessionModel) -> dict:
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    prefs = json.loads(profile.preferences_json) if profile else {}
    hard_limits = json.loads(profile.hard_limits_json) if profile else []
    reaction = json.loads(profile.reaction_patterns_json) if profile else {}
    needs = json.loads(profile.needs_json) if profile else {}
    return {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "persona_name": persona.name if persona else None,
        "player_nickname": profile.nickname if profile else None,
        "player_avatar_media_id": profile.avatar_media_id if profile else None,
        "experience_level": profile.experience_level if profile else None,
        "min_duration_seconds": session_obj.min_duration_seconds,
        "max_duration_seconds": session_obj.max_duration_seconds,
        "hygiene_limit_daily": session_obj.hygiene_limit_daily,
        "hygiene_limit_weekly": session_obj.hygiene_limit_weekly,
        "hygiene_limit_monthly": session_obj.hygiene_limit_monthly,
        "hygiene_opening_max_duration_seconds": session_obj.hygiene_opening_max_duration_seconds,
        "wearer_style": prefs.get("wearer_style"),
        "wearer_goal": prefs.get("wearer_goal"),
        "wearer_boundary": prefs.get("wearer_boundary"),
        "scenario_preset": prefs.get("scenario_preset"),
        "contract_preferences": normalize_contract_preferences(prefs.get("contract")),
        "hard_limits": hard_limits,
        "penalty_multiplier": reaction.get("penalty_multiplier", 1.0),
        "gentle_mode": bool(needs.get("gentle_mode")),
        "llm": {
            "provider": session_obj.llm_provider,
            "api_url": session_obj.llm_api_url,
            "chat_model": session_obj.llm_chat_model,
            "vision_model": session_obj.llm_vision_model,
            "active": bool(session_obj.llm_profile_active),
            "api_key_stored": bool(session_obj.llm_api_key),
        },
        "roleplay_state": build_roleplay_state(
            relationship_json=session_obj.relationship_state_json,
            protocol_json=session_obj.protocol_state_json,
            scene_json=session_obj.scene_state_json,
            scenario_title=prefs.get("scenario_preset"),
            active_phase=_resolve_active_scenario_phase(db, prefs.get("scenario_preset"), prefs.get("scenario_phase_id")),
        ),
    }


def _rebuild_contract_preview(
    db: Session,
    *,
    session_obj: SessionModel,
    contract: Contract,
    persona: Persona | None,
    profile: PlayerProfile | None,
    seal_number: str | None = None,
) -> None:
    prefs = _load_json_dict(profile.preferences_json if profile else "{}")
    hard_limits = json.loads(profile.hard_limits_json) if profile and profile.hard_limits_json else []
    contract.content_text = build_contract_text(
        persona_name=persona.name if persona else "Keyholderin",
        player_nickname=profile.nickname if profile else "Wearer",
        min_duration_seconds=session_obj.min_duration_seconds,
        max_duration_seconds=session_obj.max_duration_seconds,
        contract_context=build_contract_context(
            keyholder_name=persona.name if persona else "Keyholderin",
            wearer_name=profile.nickname if profile else "Wearer",
            min_duration_seconds=session_obj.min_duration_seconds,
            max_duration_seconds=session_obj.max_duration_seconds,
            contract_preferences=prefs.get("contract"),
            hard_limits=hard_limits,
            scenario_title=prefs.get("scenario_preset"),
            seal_number=seal_number,
            hygiene_opening_max_duration_seconds=session_obj.hygiene_opening_max_duration_seconds,
        ),
        session_obj=session_obj,
    )
    db.add(contract)


@router.get("/blueprints/completed")
def list_completed_blueprints(request: Request, db: Session = Depends(get_db)) -> dict:
    current_user = get_current_session_user(request, db)
    query = (
        db.query(SessionModel)
        .join(PlayerProfile, PlayerProfile.id == SessionModel.player_profile_id)
        .filter(SessionModel.status == "completed")
    )
    if current_user is not None:
        query = query.filter(PlayerProfile.auth_user_id == current_user.id)
    else:
        query = query.filter(PlayerProfile.auth_user_id.is_(None))
    rows = query.order_by(SessionModel.id.desc()).limit(50).all()
    items = []
    for row in rows:
        persona = db.query(Persona).filter(Persona.id == row.persona_id).first()
        profile = db.query(PlayerProfile).filter(PlayerProfile.id == row.player_profile_id).first()
        items.append({
            "session_id": row.id,
            "persona_name": persona.name if persona else "Persona",
            "player_nickname": profile.nickname if profile else "Player",
            "completed_at": str(row.lock_end_actual or row.updated_at),
        })
    return {"items": items}


@router.put("/{session_id}/draft")
def update_draft_session(
    session_id: int,
    payload: CreateSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    if session_obj.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft sessions can be updated")

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    current_persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    persona = _resolve_persona_for_session(payload, db, current_persona=current_persona)
    session_obj.persona_id = persona.id

    prefs = _load_json_dict(profile.preferences_json)
    if payload.scenario_preset is not None:
        prefs["scenario_preset"] = payload.scenario_preset
    active_phase = _resolve_active_scenario_phase(
        db,
        prefs.get("scenario_preset"),
        prefs.get("scenario_phase_id"),
    )
    if active_phase is not None:
        active_phase_id = str(active_phase.get("phase_id") or "").strip()
        if active_phase_id:
            prefs["scenario_phase_id"] = active_phase_id
        prefs["scenario_phase_progress"] = 0
    if payload.wearer_style is not None:
        prefs["wearer_style"] = payload.wearer_style
    if payload.wearer_goal is not None:
        prefs["wearer_goal"] = payload.wearer_goal
    if payload.wearer_boundary is not None:
        prefs["wearer_boundary"] = payload.wearer_boundary
    contract_prefs = normalize_contract_preferences(prefs.get("contract"))
    contract_mapping = {
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
    for key, value in contract_mapping.items():
        if value is None:
            continue
        contract_prefs[key] = str(value).strip()
    prefs["contract"] = normalize_contract_preferences(contract_prefs)

    profile.nickname = str(payload.player_nickname or "").strip()[:120] or profile.nickname
    if payload.experience_level:
        profile.experience_level = payload.experience_level
    if payload.hard_limits is not None:
        profile.hard_limits_json = json.dumps(payload.hard_limits)
    profile.preferences_json = json.dumps(prefs)

    if payload.min_duration_seconds is not None:
        session_obj.min_duration_seconds = int(payload.min_duration_seconds)
    if payload.max_duration_seconds is not None or payload.max_duration_seconds is None:
        session_obj.max_duration_seconds = payload.max_duration_seconds
    session_obj.hygiene_limit_daily = payload.hygiene_limit_daily
    session_obj.hygiene_limit_weekly = payload.hygiene_limit_weekly
    session_obj.hygiene_limit_monthly = payload.hygiene_limit_monthly
    if payload.hygiene_opening_max_duration_seconds is not None:
        session_obj.hygiene_opening_max_duration_seconds = int(payload.hygiene_opening_max_duration_seconds)
    session_obj.llm_provider = payload.llm_provider
    session_obj.llm_api_url = payload.llm_api_url
    session_obj.llm_api_key = payload.llm_api_key
    session_obj.llm_chat_model = payload.llm_chat_model
    session_obj.llm_vision_model = payload.llm_vision_model
    session_obj.llm_profile_active = bool(payload.llm_active) if payload.llm_active is not None else session_obj.llm_profile_active

    seal_number = str(payload.initial_seal_number or "").strip() or None
    _rebuild_contract_preview(
        db,
        session_obj=session_obj,
        contract=contract,
        persona=persona,
        profile=profile,
        seal_number=seal_number,
    )

    db.add(profile)
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    db.refresh(contract)

    return {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "ws_auth_token": session_obj.ws_auth_token,
        "contract_required": True,
        "contract_preview": contract.content_text,
        "updated": True,
        "llm_session": {
            "provider": session_obj.llm_provider,
            "api_url": session_obj.llm_api_url,
            "chat_model": session_obj.llm_chat_model,
            "vision_model": session_obj.llm_vision_model,
            "active": bool(session_obj.llm_profile_active),
        },
    }


@router.put("/{session_id}/persona")
def update_session_persona(
    session_id: int,
    payload: UpdateSessionPersonaRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    persona = db.query(Persona).filter(Persona.id == payload.persona_id).first()
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")

    session_obj.persona_id = persona.id
    db.add(session_obj)
    db.commit()

    audit_log("session_persona_reassigned", session_id=session_obj.id, persona_id=persona.id, persona_name=persona.name)
    return {
        "ok": True,
        "session_id": session_obj.id,
        "persona_id": persona.id,
        "persona_name": persona.name,
    }


@router.get("/blueprints/{session_id}")
def get_completed_blueprint(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    if session_obj.status != "completed":
        raise HTTPException(status_code=409, detail="Blueprint nur fuer abgeschlossene Sessions verfuegbar")
    return _session_blueprint(db, session_obj)


@router.get("/{session_id}")
def get_session(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not session_obj.ws_auth_token:
        _ensure_ws_auth_token(session_obj)
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    prefs = _load_json_dict(profile.preferences_json if profile else None)
    roleplay_state = build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=prefs.get("scenario_preset"),
        active_phase=_resolve_active_scenario_phase(db, prefs.get("scenario_preset"), prefs.get("scenario_phase_id")),
    )
    relationship_memory = build_relationship_memory(db, session_obj)

    return {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "min_duration_seconds": session_obj.min_duration_seconds,
        "max_duration_seconds": session_obj.max_duration_seconds,
        "hygiene_limit_daily": session_obj.hygiene_limit_daily,
        "hygiene_limit_weekly": session_obj.hygiene_limit_weekly,
        "hygiene_limit_monthly": session_obj.hygiene_limit_monthly,
        "hygiene_opening_max_duration_seconds": session_obj.hygiene_opening_max_duration_seconds,
        "llm_session": {
            "provider": session_obj.llm_provider,
            "api_url": session_obj.llm_api_url,
            "chat_model": session_obj.llm_chat_model,
            "vision_model": session_obj.llm_vision_model,
            "active": bool(session_obj.llm_profile_active),
            "api_key_stored": bool(session_obj.llm_api_key),
        },
        "lock_start": str(session_obj.lock_start) if session_obj.lock_start else None,
        "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
        "ws_auth_token": session_obj.ws_auth_token,
        "contract_signed": bool(contract and contract.signed_at),
        "roleplay_state": roleplay_state,
        "relationship_memory": relationship_memory,
        "player_profile": {
            "id": profile.id,
            "experience_level": profile.experience_level,
            "preferences": json.loads(profile.preferences_json),
            "soft_limits": json.loads(profile.soft_limits_json),
            "hard_limits": json.loads(profile.hard_limits_json),
            "reaction_patterns": json.loads(profile.reaction_patterns_json),
            "needs": json.loads(profile.needs_json),
        }
        if profile
        else None,
    }


@router.put("/{session_id}/player-profile")
def update_player_profile(
    session_id: int,
    payload: UpdatePlayerProfileRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)

    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    if payload.experience_level is not None:
        profile.experience_level = payload.experience_level
    if payload.preferences is not None:
        profile.preferences_json = json.dumps(payload.preferences)
    if payload.soft_limits is not None:
        profile.soft_limits_json = json.dumps(payload.soft_limits)
    if payload.hard_limits is not None:
        profile.hard_limits_json = json.dumps(payload.hard_limits)
    if payload.reaction_patterns is not None:
        profile.reaction_patterns_json = json.dumps(payload.reaction_patterns)
    if payload.needs is not None:
        profile.needs_json = json.dumps(payload.needs)
    if payload.clear_avatar:
        profile.avatar_media_id = None
    elif payload.avatar_media_id is not None:
        _ensure_avatar_exists(db, payload.avatar_media_id)
        profile.avatar_media_id = payload.avatar_media_id

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {
        "session_id": session_id,
        "player_profile": {
            "id": profile.id,
            "avatar_media_id": profile.avatar_media_id,
            "avatar_url": f"/api/media/{profile.avatar_media_id}/content" if profile.avatar_media_id else None,
            "experience_level": profile.experience_level,
            "preferences": json.loads(profile.preferences_json),
            "soft_limits": json.loads(profile.soft_limits_json),
            "hard_limits": json.loads(profile.hard_limits_json),
            "reaction_patterns": json.loads(profile.reaction_patterns_json),
            "needs": json.loads(profile.needs_json),
        },
    }


@router.get("/{session_id}/seal-history")
def get_seal_history(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    get_owned_session(request, db, session_id)

    entries = (
        db.query(SealHistory)
        .filter(SealHistory.session_id == session_id)
        .order_by(SealHistory.id.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "entries": [
            {
                "id": entry.id,
                "seal_number": entry.seal_number,
                "status": entry.status,
                "note": entry.note,
                "applied_at": str(entry.applied_at),
            }
            for entry in entries
        ],
    }


def _collect_session_events(db: Session, session_id: int) -> list[tuple[datetime, dict]]:
    events: list[tuple[datetime, dict]] = []

    message_rows = db.query(Message).filter(Message.session_id == session_id).all()
    for row in message_rows:
        occurred_at = _as_utc(row.created_at)
        events.append(
            (
                occurred_at,
                {
                    "source": "message",
                    "event_type": row.message_type,
                    "occurred_at": str(row.created_at),
                    "data": {
                        "id": row.id,
                        "role": row.role,
                        "content": row.content,
                    },
                },
            )
        )

    safety_rows = db.query(SafetyLog).filter(SafetyLog.session_id == session_id).all()
    for row in safety_rows:
        occurred_at = _as_utc(row.created_at)
        events.append(
            (
                occurred_at,
                {
                    "source": "safety",
                    "event_type": row.event_type,
                    "occurred_at": str(row.created_at),
                    "data": {
                        "id": row.id,
                        "reason": row.reason,
                    },
                },
            )
        )

    hygiene_rows = db.query(HygieneOpening).filter(HygieneOpening.session_id == session_id).all()
    for row in hygiene_rows:
        ts = row.opened_at or row.requested_at or datetime.now(timezone.utc)
        occurred_at = _as_utc(ts)
        events.append(
            (
                occurred_at,
                {
                    "source": "hygiene",
                    "event_type": row.status,
                    "occurred_at": str(ts),
                    "data": {
                        "id": row.id,
                        "overrun_seconds": row.overrun_seconds,
                        "penalty_seconds": row.penalty_seconds,
                    },
                },
            )
        )

    task_rows = db.query(Task).filter(Task.session_id == session_id).all()
    for row in task_rows:
        ts = row.completed_at or row.consequence_applied_at or row.created_at or datetime.now(timezone.utc)
        occurred_at = _as_utc(ts)
        events.append(
            (
                occurred_at,
                {
                    "source": "task",
                    "event_type": row.status,
                    "occurred_at": str(ts),
                    "data": {
                        "id": row.id,
                        "title": row.title,
                        "consequence_applied_seconds": row.consequence_applied_seconds,
                    },
                },
            )
        )

    verification_rows = db.query(Verification).filter(Verification.session_id == session_id).all()
    for row in verification_rows:
        ts = row.created_at or row.requested_at or datetime.now(timezone.utc)
        occurred_at = _as_utc(ts)
        events.append(
            (
                occurred_at,
                {
                    "source": "verification",
                    "event_type": row.status,
                    "occurred_at": str(ts),
                    "data": {
                        "id": row.id,
                        "requested_seal_number": row.requested_seal_number,
                        "observed_seal_number": row.observed_seal_number,
                    },
                },
            )
        )

    events.sort(key=lambda item: item[0])
    return events


@router.get("/{session_id}/events")
def get_session_events(
    session_id: int,
    request: Request,
    source: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)

    events = [item for _, item in _collect_session_events(db, session_id)]
    if source:
        events = [item for item in events if item["source"] == source]
    if event_type:
        events = [item for item in events if item["event_type"] == event_type]
    events = events[:limit]

    return {
        "session_id": session_id,
        "session_status": session_obj.status,
        "items": events,
    }


@router.get("/{session_id}/events/export")
def export_session_events(
    session_id: int,
    request: Request,
    format: str = Query(default="text", pattern="^(text|json)$"),
    source: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    payload = get_session_events(
        session_id=session_id,
        request=request,
        source=source,
        event_type=event_type,
        limit=limit,
        db=db,
    )
    if format == "json":
        return payload

    lines = [f"session_id={payload['session_id']} status={payload['session_status']}"]
    for item in payload["items"]:
        lines.append(
            f"{item['occurred_at']} | source={item['source']} | type={item['event_type']} | data={json.dumps(item['data'])}"
        )
    return PlainTextResponse("\n".join(lines))


def _session_export_lines(payload: dict) -> list[str]:
    lines = [
        f"session_id={payload['session_id']}",
        f"status={payload['session_status']}",
        f"event_count={len(payload['items'])}",
        "",
        "EVENTS:",
    ]
    for item in payload["items"]:
        lines.append(
            f"{item['occurred_at']} | source={item['source']} | type={item['event_type']} | data={json.dumps(item['data'])}"
        )
    return lines


@router.get("/{session_id}/export")
def export_session_snapshot(
    session_id: int,
    request: Request,
    format: str = Query(default="text", pattern="^(text|json|pdf)$"),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    payload = get_session_events(session_id=session_id, request=request, source=None, event_type=None, limit=limit, db=db)

    if format == "json":
        return payload

    lines = _session_export_lines(payload)
    if format == "text":
        return PlainTextResponse("\n".join(lines))

    pdf_bytes = build_simple_text_pdf(lines)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="session-{session_id}.pdf"',
        },
    )


@router.get("/{session_id}/contract")
def get_contract(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    addenda = (
        db.query(ContractAddendum)
        .filter(ContractAddendum.contract_id == contract.id)
        .order_by(ContractAddendum.id.asc())
        .all()
    )

    return {
        "session_id": session_id,
        "contract": {
            "id": contract.id,
            "content_text": contract.content_text,
            "signed_at": str(contract.signed_at) if contract.signed_at else None,
            "parameters_snapshot": contract.parameters_snapshot,
            "created_at": str(contract.created_at),
        },
        "addenda": [
            _addendum_payload(item, session_obj=session_obj, profile=profile)
            for item in addenda
        ],
    }


@router.get("/{session_id}/contract/export")
def export_contract(
    session_id: int,
    request: Request,
    format: str = Query(default="text", pattern="^(text|json)$"),
    db: Session = Depends(get_db),
):
    payload = get_contract(session_id=session_id, request=request, db=db)
    if format == "json":
        return payload

    contract = payload["contract"]
    lines = [
        f"session_id={payload['session_id']}",
        f"contract_id={contract['id']}",
        f"signed_at={contract['signed_at']}",
        "",
        "CONTENT:",
        contract["content_text"],
        "",
        "ADDENDA:",
    ]
    for item in payload["addenda"]:
        lines.append(
            f"- #{item['id']} consent={item['player_consent']} desc={item['change_description']} changes={json.dumps(item['proposed_changes'])}"
        )

    return PlainTextResponse("\n".join(lines))


@router.post("")
def create_session(payload: CreateSessionRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    current_user = get_current_session_user(request, db)
    template_session = None
    template_persona = None
    template_profile = None
    if payload.template_session_id:
        template_session = get_accessible_session(db, payload.template_session_id, current_user)
        if template_session.status != "completed":
            raise HTTPException(status_code=409, detail="Template session is not completed")
        template_persona = db.query(Persona).filter(Persona.id == template_session.persona_id).first()
        template_profile = db.query(PlayerProfile).filter(PlayerProfile.id == template_session.player_profile_id).first()

    persona_name = payload.persona_name or (template_persona.name if template_persona else None)
    player_nickname = payload.player_nickname or (template_profile.nickname if template_profile else None)
    min_duration_seconds = payload.min_duration_seconds or (template_session.min_duration_seconds if template_session else None)
    _missing: list[dict] = []
    if not persona_name:
        _missing.append({"type": "missing", "loc": ("body", "persona_name"), "msg": "Field required", "input": None})
    if not player_nickname:
        _missing.append({"type": "missing", "loc": ("body", "player_nickname"), "msg": "Field required", "input": None})
    if not min_duration_seconds:
        _missing.append({"type": "missing", "loc": ("body", "min_duration_seconds"), "msg": "Field required", "input": None})
    if _missing:
        raise RequestValidationError(errors=_missing)

    persona = _resolve_persona_for_session(payload, db, current_persona=None)

    template_prefs = {}
    template_hard_limits = []
    template_reaction = {}
    template_needs = {}
    if template_profile:
        template_prefs = json.loads(template_profile.preferences_json or "{}")
        template_hard_limits = json.loads(template_profile.hard_limits_json or "[]")
        template_reaction = json.loads(template_profile.reaction_patterns_json or "{}")
        template_needs = json.loads(template_profile.needs_json or "{}")

    prefs: dict = dict(template_prefs)
    if payload.scenario_preset is not None:
        prefs["scenario_preset"] = payload.scenario_preset
    active_phase = _resolve_active_scenario_phase(
        db,
        prefs.get("scenario_preset"),
        prefs.get("scenario_phase_id"),
    )
    if active_phase is not None:
        active_phase_id = str(active_phase.get("phase_id") or "").strip()
        if active_phase_id:
            prefs["scenario_phase_id"] = active_phase_id
        prefs["scenario_phase_progress"] = 0
    if payload.wearer_style is not None:
        prefs["wearer_style"] = payload.wearer_style
    if payload.wearer_goal is not None:
        prefs["wearer_goal"] = payload.wearer_goal
    if payload.wearer_boundary is not None:
        prefs["wearer_boundary"] = payload.wearer_boundary
    contract_prefs = normalize_contract_preferences(prefs.get("contract"))
    contract_mapping = {
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
    for key, value in contract_mapping.items():
        if value is None:
            continue
        contract_prefs[key] = str(value).strip()
    prefs["contract"] = normalize_contract_preferences(contract_prefs)

    experience_level = payload.experience_level or (template_profile.experience_level if template_profile else "beginner")
    effective_hard_limits = payload.hard_limits if payload.hard_limits is not None else template_hard_limits

    player = PlayerProfile(
        auth_user_id=current_user.id if current_user else None,
        nickname=player_nickname,
        experience_level=experience_level,
        preferences_json=json.dumps(prefs),
        hard_limits_json=json.dumps(effective_hard_limits),
        reaction_patterns_json=json.dumps(template_reaction),
        needs_json=json.dumps(template_needs),
        avatar_media_id=template_profile.avatar_media_id if template_profile else None,
    )
    db.add(player)
    db.flush()

    max_duration_seconds = payload.max_duration_seconds
    if max_duration_seconds is None and template_session:
        max_duration_seconds = template_session.max_duration_seconds
    hygiene_limit_daily = payload.hygiene_limit_daily if payload.hygiene_limit_daily is not None else (template_session.hygiene_limit_daily if template_session else None)
    hygiene_limit_weekly = payload.hygiene_limit_weekly if payload.hygiene_limit_weekly is not None else (template_session.hygiene_limit_weekly if template_session else None)
    hygiene_limit_monthly = payload.hygiene_limit_monthly if payload.hygiene_limit_monthly is not None else (template_session.hygiene_limit_monthly if template_session else None)
    hygiene_opening_max_duration_seconds = (
        payload.hygiene_opening_max_duration_seconds
        if payload.hygiene_opening_max_duration_seconds is not None
        else (
            template_session.hygiene_opening_max_duration_seconds
            if template_session and template_session.hygiene_opening_max_duration_seconds is not None
            else settings.hygiene_opening_max_duration_seconds
        )
    )

    default_llm = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    llm_provider = payload.llm_provider if payload.llm_provider is not None else (template_session.llm_provider if template_session else (default_llm.provider if default_llm else None))
    llm_api_url = payload.llm_api_url if payload.llm_api_url is not None else (template_session.llm_api_url if template_session else (default_llm.api_url if default_llm else None))
    llm_api_key = payload.llm_api_key if payload.llm_api_key is not None else (template_session.llm_api_key if template_session else (default_llm.api_key if default_llm else None))
    llm_chat_model = payload.llm_chat_model if payload.llm_chat_model is not None else (template_session.llm_chat_model if template_session else (default_llm.chat_model if default_llm else None))
    llm_vision_model = payload.llm_vision_model if payload.llm_vision_model is not None else (template_session.llm_vision_model if template_session else (default_llm.vision_model if default_llm else None))
    llm_active = payload.llm_active if payload.llm_active is not None else (bool(template_session.llm_profile_active) if template_session else bool(default_llm.profile_active if default_llm else False))
    initial_roleplay_behavior = behavior_profile_from_entities(
        persona=persona,
        scenario=db.query(Scenario).filter(Scenario.key == prefs.get("scenario_preset")).first() if prefs.get("scenario_preset") else None,
    )
    if not initial_roleplay_behavior:
        initial_roleplay_behavior = behavior_profile_from_scenario_key(db, prefs.get("scenario_preset"))
    initial_roleplay_state = initialize_roleplay_state(
        scenario_title=prefs.get("scenario_preset"),
        active_phase=active_phase,
        behavior_profile=initial_roleplay_behavior,
    )

    session_obj = SessionModel(
        persona_id=persona.id,
        player_profile_id=player.id,
        min_duration_seconds=min_duration_seconds,
        max_duration_seconds=max_duration_seconds,
        hygiene_limit_daily=hygiene_limit_daily,
        hygiene_limit_weekly=hygiene_limit_weekly,
        hygiene_limit_monthly=hygiene_limit_monthly,
        hygiene_opening_max_duration_seconds=hygiene_opening_max_duration_seconds,
        llm_provider=llm_provider,
        llm_api_url=llm_api_url,
        llm_api_key=llm_api_key,
        llm_chat_model=llm_chat_model,
        llm_vision_model=llm_vision_model,
        llm_profile_active=bool(llm_active),
        relationship_state_json=initial_roleplay_state["relationship_state_json"],
        protocol_state_json=initial_roleplay_state["protocol_state_json"],
        scene_state_json=initial_roleplay_state["scene_state_json"],
        status="draft",
    )
    _ensure_ws_auth_token(session_obj)
    db.add(session_obj)
    db.flush()

    if current_user is not None:
        if current_user.default_player_profile_id is None:
            current_user.default_player_profile_id = player.id
        current_user.active_session_id = session_obj.id
        db.add(current_user)

    contract = Contract(
        session_id=session_obj.id,
        content_text="",
        parameters_snapshot="{}",
    )
    db.add(contract)
    _rebuild_contract_preview(
        db,
        session_obj=session_obj,
        contract=contract,
        persona=persona,
        profile=player,
        seal_number=payload.initial_seal_number,
    )

    if payload.initial_seal_number:
        seal = SealHistory(
            session_id=session_obj.id,
            seal_number=payload.initial_seal_number,
            status="active",
        )
        db.add(seal)

    db.commit()
    db.refresh(session_obj)

    return {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "ws_auth_token": session_obj.ws_auth_token,
        "contract_required": True,
        "contract_preview": contract.content_text,
        "llm_session": {
            "provider": session_obj.llm_provider,
            "api_url": session_obj.llm_api_url,
            "chat_model": session_obj.llm_chat_model,
            "vision_model": session_obj.llm_vision_model,
            "active": bool(session_obj.llm_profile_active),
        },
    }


@router.post("/{session_id}/sign-contract")
def sign_contract(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    current_user = get_current_session_user(request, db)

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.signed_at:
        if current_user is not None:
            bind_session_profile_to_user(db, session_obj, current_user)
            current_user.active_session_id = session_obj.id
            db.add(current_user)
        if not session_obj.ws_auth_token:
            _ensure_ws_auth_token(session_obj)
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)
        return {
            "session_id": session_id,
            "status": session_obj.status,
            "ws_auth_token": session_obj.ws_auth_token,
            "already_signed": True,
        }

    updated = SessionService.sign_contract_and_start(db=db, session_obj=session_obj, contract_obj=contract)
    persona = db.query(Persona).filter(Persona.id == updated.persona_id).first()
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == updated.player_profile_id).first()
    profile_prefs = _load_json_dict(profile.preferences_json if profile else "{}")
    try:
        snapshot = json.loads(contract.parameters_snapshot or "{}")
    except Exception:
        snapshot = {}
    selected_duration_seconds = snapshot.get("selected_duration_seconds")
    contract.content_text = build_contract_text(
        persona_name=persona.name if persona else "Keyholderin",
        player_nickname=profile.nickname if profile else "Wearer",
        min_duration_seconds=updated.min_duration_seconds,
        max_duration_seconds=updated.max_duration_seconds,
        contract_context=build_contract_context(
            keyholder_name=persona.name if persona else "Keyholderin",
            wearer_name=profile.nickname if profile else "Wearer",
            min_duration_seconds=updated.min_duration_seconds,
            max_duration_seconds=updated.max_duration_seconds,
            contract_preferences=profile_prefs.get("contract"),
            hard_limits=json.loads(profile.hard_limits_json) if profile and profile.hard_limits_json else [],
            scenario_title=profile_prefs.get("scenario_preset"),
            hygiene_opening_max_duration_seconds=updated.hygiene_opening_max_duration_seconds,
            reference_at=contract.signed_at,
            selected_duration_seconds=selected_duration_seconds if isinstance(selected_duration_seconds, int) else None,
        ),
        session_obj=updated,
    )
    db.add(contract)
    if current_user is not None:
        bind_session_profile_to_user(db, updated, current_user)
        if current_user.default_player_profile_id is None:
            current_user.default_player_profile_id = updated.player_profile_id
        current_user.active_session_id = updated.id
        db.add(current_user)
    _ensure_ws_auth_token(updated)
    db.add(updated)
    db.commit()
    db.refresh(updated)
    audit_log("contract_signed", session_id=session_id, status=updated.status)
    return {
        "session_id": updated.id,
        "status": updated.status,
        "lock_end": str(updated.lock_end),
        "ws_auth_token": updated.ws_auth_token,
    }


@router.post("/{session_id}/chat/ws-token/rotate")
def rotate_chat_ws_token(
    session_id: int,
    _admin_user = Depends(require_admin_session_user),
    _: None = Depends(verify_admin_secret),
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    _rotate_ws_auth_token(session_obj)
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return {
        "session_id": session_obj.id,
        "ws_auth_token": session_obj.ws_auth_token,
        "rotated_at": str(session_obj.ws_auth_token_created_at),
    }


@router.get("/{session_id}/timer")
def get_timer_state(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)

    now = datetime.now(timezone.utc)
    return {
        "session_id": session_id,
        "status": session_obj.status,
        "timer_frozen": session_obj.timer_frozen,
        "remaining_seconds": _remaining_seconds(session_obj, now),
        "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
    }


@router.post("/{session_id}/timer/add")
def add_timer_time(session_id: int, payload: TimerAdjustRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    session_obj.lock_end = _as_utc(session_obj.lock_end) + timedelta(seconds=payload.seconds)
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    return {
        "session_id": session_id,
        "lock_end": str(session_obj.lock_end),
        "remaining_seconds": _remaining_seconds(session_obj, datetime.now(timezone.utc)),
    }


@router.post("/{session_id}/timer/remove")
def remove_timer_time(session_id: int, payload: TimerAdjustRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    now = datetime.now(timezone.utc)
    floor = _as_utc(session_obj.freeze_start) if session_obj.timer_frozen and session_obj.freeze_start else now
    session_obj.lock_end = max(floor, _as_utc(session_obj.lock_end) - timedelta(seconds=payload.seconds))
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    return {
        "session_id": session_id,
        "lock_end": str(session_obj.lock_end),
        "remaining_seconds": _remaining_seconds(session_obj, now),
    }


@router.post("/{session_id}/timer/freeze")
def freeze_timer(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    if not session_obj.timer_frozen:
        session_obj.timer_frozen = True
        session_obj.freeze_start = datetime.now(timezone.utc)
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)

    return {
        "session_id": session_id,
        "timer_frozen": session_obj.timer_frozen,
        "freeze_start": str(session_obj.freeze_start) if session_obj.freeze_start else None,
    }


@router.post("/{session_id}/timer/unfreeze")
def unfreeze_timer(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    now = datetime.now(timezone.utc)
    if session_obj.timer_frozen and session_obj.freeze_start is not None:
        frozen_for = now - _as_utc(session_obj.freeze_start)
        session_obj.lock_end = _as_utc(session_obj.lock_end) + frozen_for
        session_obj.timer_frozen = False
        session_obj.freeze_start = None
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)

    return {
        "session_id": session_id,
        "timer_frozen": session_obj.timer_frozen,
        "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
        "remaining_seconds": _remaining_seconds(session_obj, now),
    }


@router.post("/{session_id}/contract/addenda")
def propose_contract_addendum(
    session_id: int,
    payload: ProposeAddendumRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.signed_at:
        raise HTTPException(status_code=400, detail="Contract must be signed before addenda")

    normalized_changes = _normalize_addendum_changes(payload.proposed_changes, session_obj=session_obj)

    addendum = ContractAddendum(
        contract_id=contract.id,
        proposed_changes_json=json.dumps(normalized_changes, ensure_ascii=False),
        change_description=payload.change_description,
        proposed_by="ai",
        player_consent="pending",
    )
    db.add(addendum)
    db.commit()
    db.refresh(addendum)

    return {
        "addendum_id": addendum.id,
        "session_id": session_id,
        "status": addendum.player_consent,
        **_build_addendum_metadata(normalized_changes, session_obj=session_obj, profile=profile),
    }


@router.post("/{session_id}/contract/addenda/{addendum_id}/consent")
def consent_contract_addendum(
    session_id: int,
    addendum_id: int,
    payload: AddendumConsentRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    addendum = (
        db.query(ContractAddendum)
        .filter(ContractAddendum.id == addendum_id, ContractAddendum.contract_id == contract.id)
        .first()
    )
    if not addendum:
        raise HTTPException(status_code=404, detail="Addendum not found")
    if addendum.player_consent != "pending":
        return {
            "addendum_id": addendum.id,
            "decision": addendum.player_consent,
            "session_id": session_id,
            "already_decided": True,
        }

    addendum.player_consent = payload.decision
    addendum.player_consent_at = datetime.now(timezone.utc)

    if payload.decision == "approved":
        proposed_changes = _normalize_addendum_changes(_load_json_dict(addendum.proposed_changes_json), session_obj=session_obj)
        previous_min = session_obj.min_duration_seconds
        previous_max = session_obj.max_duration_seconds
        reaction = _load_json_dict(profile.reaction_patterns_json if profile else "{}")
        applied_summary: list[str] = []

        for key, value in proposed_changes.items():
            if key in ADDENDUM_SESSION_INT_FIELDS:
                setattr(session_obj, key, int(value))
                applied_summary.append(f"{ADDENDUM_SUPPORTED_FIELDS[key]['label']}: {value}")
            elif key in ADDENDUM_REACTION_FIELDS:
                reaction[key] = value
                applied_summary.append(f"{ADDENDUM_SUPPORTED_FIELDS[key]['label']}: {value}")

        if session_obj.status == "active" and session_obj.lock_start is not None and session_obj.lock_end is not None:
            current_duration_seconds = int((session_obj.lock_end - session_obj.lock_start).total_seconds())
            duration_inputs_changed = (
                session_obj.min_duration_seconds != previous_min
                or session_obj.max_duration_seconds != previous_max
            )
            next_duration_seconds = current_duration_seconds
            if duration_inputs_changed:
                next_duration_seconds = SessionService.clamp_active_duration_seconds(
                    current_duration_seconds=current_duration_seconds,
                    min_duration_seconds=session_obj.min_duration_seconds,
                    max_duration_seconds=session_obj.max_duration_seconds,
                )
                if next_duration_seconds != current_duration_seconds:
                    applied_summary.append(
                        f"Aktive Sessiondauer geklemmt: {current_duration_seconds}s -> {next_duration_seconds}s"
                    )
            session_obj.lock_end = session_obj.lock_start + timedelta(seconds=next_duration_seconds)

        protocol_notes = _apply_protocol_addendum(db, session_obj, proposed_changes)
        applied_summary.extend(protocol_notes)

        if profile is not None and reaction != _load_json_dict(profile.reaction_patterns_json):
            profile.reaction_patterns_json = json.dumps(reaction, ensure_ascii=False)
            db.add(profile)

        if session_obj.min_duration_seconds != previous_min or session_obj.max_duration_seconds != previous_max:
            persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
            profile_prefs = _load_json_dict(profile.preferences_json if profile else "{}")
            contract.content_text = build_contract_text(
                persona_name=persona.name if persona else "Keyholderin",
                player_nickname=profile.nickname if profile else "Wearer",
                min_duration_seconds=session_obj.min_duration_seconds,
                max_duration_seconds=session_obj.max_duration_seconds,
                contract_context=build_contract_context(
                    keyholder_name=persona.name if persona else "Keyholderin",
                    wearer_name=profile.nickname if profile else "Wearer",
                    min_duration_seconds=session_obj.min_duration_seconds,
                    max_duration_seconds=session_obj.max_duration_seconds,
                    contract_preferences=profile_prefs.get("contract"),
                    hard_limits=json.loads(profile.hard_limits_json) if profile and profile.hard_limits_json else [],
                    scenario_title=profile_prefs.get("scenario_preset"),
                    hygiene_opening_max_duration_seconds=session_obj.hygiene_opening_max_duration_seconds,
                ),
                session_obj=session_obj,
            )
            db.add(contract)

        if applied_summary:
            db.add(
                Message(
                    session_id=session_id,
                    role="system",
                    message_type="contract_addendum_applied",
                    content=(
                        f"Vertrags-Addendum #{addendum.id} genehmigt. "
                        f"{'; '.join(applied_summary[:8])}. "
                        "Die verbleibende Restzeit bleibt task- und ereignisgesteuert; "
                        "nur Min/Max koennen die aktuelle Sessiondauer bei Bedarf begrenzen."
                    ),
                )
            )
        db.add(session_obj)

    db.add(addendum)
    db.commit()
    db.refresh(addendum)

    return {
        "addendum_id": addendum.id,
        "session_id": session_id,
        "decision": addendum.player_consent,
        "consented_at": str(addendum.player_consent_at) if addendum.player_consent_at else None,
        **_build_addendum_metadata(_load_json_dict(addendum.proposed_changes_json), session_obj=session_obj, profile=profile),
    }
