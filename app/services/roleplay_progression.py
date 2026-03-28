import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.scenario import Scenario
from app.models.session import Session as SessionModel
from app.services.behavior_profile import behavior_profile_from_entities, behavior_profile_from_scenario_key, progression_profile_from_behavior
from app.services.roleplay_state import (
    build_roleplay_state,
    merge_roleplay_state,
    serialize_roleplay_state,
    summarize_roleplay_state_changes,
)


_PHASE_SUCCESS_EVENTS = {"task_completed", "verification_confirmed"}
_PHASE_RESET_EVENTS = {"task_failed", "verification_suspicious"}


def _scenario_title_for_session(db: Session, session_obj: SessionModel) -> str | None:
    if not session_obj.player_profile_id:
        return None
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if not profile or not profile.preferences_json:
        return None
    try:
        prefs = json.loads(profile.preferences_json)
    except Exception:
        return None
    if not isinstance(prefs, dict):
        return None
    value = str(prefs.get("scenario_preset") or "").strip()
    return value[:120] if value else None


def _scenario_profile_and_prefs(db: Session, session_obj: SessionModel) -> tuple[PlayerProfile | None, dict[str, Any]]:
    if not session_obj.player_profile_id:
        return None, {}
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if not profile or not profile.preferences_json:
        return profile, {}
    try:
        prefs = json.loads(profile.preferences_json)
    except Exception:
        return profile, {}
    return profile, prefs if isinstance(prefs, dict) else {}


def _scenario_phases_for_session(db: Session, session_obj: SessionModel) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profile, prefs = _scenario_profile_and_prefs(db, session_obj)
    scenario_key = str(prefs.get("scenario_preset") or "").strip()
    if not scenario_key:
        return [], prefs

    scenario = db.query(Scenario).filter(Scenario.key == scenario_key).first()
    phases: list[dict[str, Any]] = []
    if scenario:
        try:
            parsed = json.loads(scenario.phases_json or "[]")
            if isinstance(parsed, list):
                phases = [item for item in parsed if isinstance(item, dict)]
        except Exception:
            phases = []
    return phases, prefs


def _active_phase_for_session(db: Session, session_obj: SessionModel) -> dict[str, Any] | None:
    phases, prefs = _scenario_phases_for_session(db, session_obj)
    if not phases:
        return None
    current_phase_id = str(prefs.get("scenario_phase_id") or "").strip()
    if current_phase_id:
        matched = next((phase for phase in phases if str(phase.get("phase_id") or "").strip() == current_phase_id), None)
        if matched is not None:
            return matched
    return phases[0]


def _advance_phase_for_event(
    db: Session,
    session_obj: SessionModel,
    *,
    event_type: str,
) -> tuple[dict[str, Any] | None, str | None]:
    phases, prefs = _scenario_phases_for_session(db, session_obj)
    profile, _ = _scenario_profile_and_prefs(db, session_obj)
    if not profile or len(phases) < 2:
        return None, None

    current_phase_id = str(prefs.get("scenario_phase_id") or "").strip()
    current_index = 0
    if current_phase_id:
        for index, phase in enumerate(phases):
            if str(phase.get("phase_id") or "").strip() == current_phase_id:
                current_index = index
                break

    current_phase = phases[current_index]
    progress = max(0, int(prefs.get("scenario_phase_progress") or 0))
    normalized = str(event_type or "").strip().lower()

    if normalized in _PHASE_SUCCESS_EVENTS:
        progress += 1
        threshold = max(1, int(current_phase.get("advance_after_successes") or 3))
        if progress >= threshold and current_index < len(phases) - 1:
            next_phase = phases[current_index + 1]
            next_phase_id = str(next_phase.get("phase_id") or "").strip()
            if next_phase_id:
                prefs["scenario_phase_id"] = next_phase_id
            prefs["scenario_phase_progress"] = 0
            profile.preferences_json = json.dumps(prefs, ensure_ascii=False)
            db.add(profile)
            return next_phase, f"Phase gewechselt: {str(next_phase.get('title') or next_phase_id or 'naechste Phase').strip()}"
        prefs["scenario_phase_progress"] = progress
        profile.preferences_json = json.dumps(prefs, ensure_ascii=False)
        db.add(profile)
        return current_phase, None

    if normalized in _PHASE_RESET_EVENTS:
        prefs["scenario_phase_progress"] = 0
        profile.preferences_json = json.dumps(prefs, ensure_ascii=False)
        db.add(profile)
        return current_phase, None

    return current_phase, None


def _clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))


def _relationship_patch(current: dict[str, Any], deltas: dict[str, int]) -> dict[str, int]:
    patch: dict[str, int] = {}
    for key, delta in deltas.items():
        try:
            current_value = int(current.get(key))
        except (TypeError, ValueError):
            continue
        next_value = _clamp_score(current_value + int(delta))
        if next_value != current_value:
            patch[key] = next_value
    return patch


def _trim_open_orders(protocol: dict[str, Any], task_title: str | None) -> list[str] | None:
    title = str(task_title or "").strip().lower()
    if not title:
        return None
    current = protocol.get("open_orders")
    if not isinstance(current, list):
        return None
    filtered = [
        str(item)
        for item in current
        if str(item).strip() and title not in str(item).strip().lower()
    ]
    if filtered == current:
        return None
    return filtered


def _patch_for_task_event(
    current_state: dict[str, dict[str, Any]],
    *,
    event_type: str,
    progression_profile: dict[str, Any],
    task_title: str | None = None,
) -> dict[str, Any] | None:
    relationship = current_state.get("relationship", {})
    protocol = current_state.get("protocol", {})
    event_patch = ((progression_profile.get("events") or {}).get(event_type) or {}) if isinstance(progression_profile, dict) else {}
    if not isinstance(event_patch, dict):
        return None
    relationship_patch = _relationship_patch(relationship, event_patch.get("relationship_deltas") or {})
    patch: dict[str, Any] = {}
    if relationship_patch:
        patch["relationship"] = relationship_patch
    if isinstance(event_patch.get("scene"), dict):
        patch["scene"] = dict(event_patch["scene"])
    if isinstance(event_patch.get("protocol"), dict):
        patch["protocol"] = dict(event_patch["protocol"])
    next_orders = _trim_open_orders(protocol, task_title)
    if next_orders is not None:
        patch["protocol"] = {**(patch.get("protocol") or {}), "open_orders": next_orders}
    return patch or None


def _patch_for_verification_event(
    current_state: dict[str, dict[str, Any]],
    *,
    status: str,
    progression_profile: dict[str, Any],
) -> dict[str, Any] | None:
    normalized = str(status or "").strip().lower()
    event_type = "verification_confirmed" if normalized == "confirmed" else ("verification_suspicious" if normalized == "suspicious" else "")
    if not event_type:
        return None
    return _patch_for_task_event(current_state, event_type=event_type, progression_profile=progression_profile, task_title=None)


def _patch_for_game_report(
    current_state: dict[str, dict[str, Any]],
    *,
    passed_steps: int,
    failed_steps: int,
    miss_count: int,
    scheduled_steps: int,
    progression_profile: dict[str, Any],
) -> dict[str, Any] | None:
    total = max(1, int(scheduled_steps or 0))
    passed = max(0, int(passed_steps or 0))
    failed = max(0, int(failed_steps or 0))
    misses = max(0, int(miss_count or 0))
    ratio = passed / total

    if ratio >= 0.8 and failed == 0 and misses <= 1:
        return _patch_for_task_event(current_state, event_type="game_report_success", progression_profile=progression_profile, task_title=None)

    if ratio <= 0.4 or failed > passed or misses >= 3:
        return _patch_for_task_event(current_state, event_type="game_report_failure", progression_profile=progression_profile, task_title=None)

    return _patch_for_task_event(current_state, event_type="game_report_mixed", progression_profile=progression_profile, task_title=None)


def roleplay_patch_for_event(
    current_state: dict[str, dict[str, Any]],
    *,
    event_type: str,
    behavior_profile: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    normalized = str(event_type or "").strip().lower()
    progression_profile = progression_profile_from_behavior(behavior_profile or {})
    if normalized in {"task_completed", "task_failed", "task_overdue"}:
        return _patch_for_task_event(current_state, event_type=normalized, progression_profile=progression_profile, task_title=kwargs.get("task_title"))
    if normalized in {"verification_confirmed", "verification_suspicious"}:
        status = "confirmed" if normalized.endswith("confirmed") else "suspicious"
        return _patch_for_verification_event(current_state, status=status, progression_profile=progression_profile)
    if normalized == "game_report":
        return _patch_for_game_report(
            current_state,
            passed_steps=int(kwargs.get("passed_steps") or 0),
            failed_steps=int(kwargs.get("failed_steps") or 0),
            miss_count=int(kwargs.get("miss_count") or 0),
            scheduled_steps=int(kwargs.get("scheduled_steps") or 0),
            progression_profile=progression_profile,
        )
    return None


def _behavior_profile_for_session(db: Session, session_obj: SessionModel) -> dict[str, Any]:
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first() if session_obj.persona_id else None
    scenario_title = _scenario_title_for_session(db, session_obj)
    scenario = db.query(Scenario).filter(Scenario.key == scenario_title).first() if scenario_title else None
    profile = behavior_profile_from_entities(persona=persona, scenario=scenario)
    if profile:
        return profile
    return behavior_profile_from_scenario_key(db, scenario_title)


def advance_roleplay_state_from_event(
    db: Session,
    session_obj: SessionModel,
    *,
    event_type: str,
    message_type: str = "session_state_updated",
    **kwargs: Any,
) -> bool:
    scenario_title = _scenario_title_for_session(db, session_obj)
    behavior_profile = _behavior_profile_for_session(db, session_obj)
    active_phase = _active_phase_for_session(db, session_obj)
    current_state = build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=scenario_title,
        active_phase=active_phase,
        behavior_profile=behavior_profile,
    )
    patch = roleplay_patch_for_event(current_state, event_type=event_type, behavior_profile=behavior_profile, **kwargs)
    phase_after_event, phase_message = _advance_phase_for_event(db, session_obj, event_type=event_type)
    if not patch and phase_after_event is None:
        return False
    if patch is None:
        patch = {}
    if phase_after_event is not None:
        patch["scene"] = {
            **(patch.get("scene") or {}),
            "title": str(phase_after_event.get("title") or "").strip(),
            "objective": str(phase_after_event.get("objective") or "").strip(),
            "pressure": str(phase_after_event.get("pressure") or "").strip(),
        }

    next_state = merge_roleplay_state(
        current_state=current_state,
        patch=patch,
        scenario_title=scenario_title,
        active_phase=phase_after_event or active_phase,
        behavior_profile=behavior_profile,
    )
    if next_state == current_state:
        return False

    serialized = serialize_roleplay_state(next_state)
    session_obj.relationship_state_json = serialized["relationship_state_json"]
    session_obj.protocol_state_json = serialized["protocol_state_json"]
    session_obj.scene_state_json = serialized["scene_state_json"]
    db.add(session_obj)
    summary = summarize_roleplay_state_changes(current_state, next_state)
    if phase_message:
        summary = f"{summary}\n{phase_message}".strip() if summary else phase_message
    db.add(
        Message(
            session_id=session_obj.id,
            role="system",
            message_type=message_type,
            content=summary,
        )
    )
    return True
