from datetime import datetime, timezone
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
    default_relationship_state,
    merge_roleplay_state,
    serialize_roleplay_state,
    summarize_roleplay_state_changes,
)


_PHASE_SCORE_KEYS = ("trust", "obedience", "resistance", "favor", "strictness", "frustration", "attachment")
_PHASE_TARGET_DEFAULTS = {
    "trust": [4, 5, 6, 7, 8, 9],
    "obedience": [5, 6, 8, 9, 10, 11],
    "resistance": [2, 3, 4, 5, 6, 6],
    "favor": [3, 4, 5, 6, 7, 8],
    "strictness": [3, 4, 5, 6, 7, 8],
    "frustration": [3, 4, 6, 7, 8, 9],
    "attachment": [3, 4, 5, 6, 7, 8],
}


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
    if not phases and scenario_key:
        from app.routers.scenarios import SCENARIO_PRESETS

        preset = next((item for item in SCENARIO_PRESETS if str(item.get("key") or "").strip() == scenario_key), None)
        raw_phases = preset.get("phases", []) if isinstance(preset, dict) else []
        if isinstance(raw_phases, list):
            phases = [item for item in raw_phases if isinstance(item, dict)]
    return phases, prefs


def _phase_duration_scale(session_obj: SessionModel) -> float:
    min_seconds = max(0, int(session_obj.min_duration_seconds or 0))
    max_seconds = max(min_seconds, int(session_obj.max_duration_seconds or 0))
    reference_seconds = max_seconds if max_seconds > min_seconds else min_seconds
    if reference_seconds <= 0:
        return 1.0
    reference_days = reference_seconds / 86400
    return max(0.75, min(1.75, reference_days / 7.0))


def _resolve_phase_targets(session_obj: SessionModel, active_phase: dict[str, Any], current_index: int) -> dict[str, int]:
    explicit = active_phase.get("score_targets") if isinstance(active_phase, dict) else None
    if isinstance(explicit, dict) and explicit:
        targets: dict[str, int] = {}
        for key in _PHASE_SCORE_KEYS:
            try:
                targets[key] = max(0, int(explicit.get(key) or 0))
            except (TypeError, ValueError):
                targets[key] = 0
        return targets

    scale = _phase_duration_scale(session_obj)
    targets: dict[str, int] = {}
    for key in _PHASE_SCORE_KEYS:
        defaults = _PHASE_TARGET_DEFAULTS.get(key) or [4]
        base = defaults[min(current_index, len(defaults) - 1)]
        targets[key] = max(1, int(round(float(base) * scale)))
    return targets


def _initialize_phase_state(session_obj: SessionModel, active_phase: dict[str, Any], current_index: int) -> dict[str, Any]:
    targets = _resolve_phase_targets(session_obj, active_phase, current_index)
    return {
        "phase_id": str(active_phase.get("phase_id") or "").strip() or None,
        "phase_index": current_index + 1,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "targets": targets,
        "scores": {key: 0 for key in _PHASE_SCORE_KEYS},
    }


def _ensure_phase_state_for_phase(
    db: Session,
    session_obj: SessionModel,
    *,
    active_phase: dict[str, Any],
    current_index: int,
) -> dict[str, Any]:
    try:
        parsed = json.loads(session_obj.phase_state_json or "{}")
    except Exception:
        parsed = {}
    phase_id = str(active_phase.get("phase_id") or "").strip() or None
    if not isinstance(parsed, dict) or parsed.get("phase_id") != phase_id:
        parsed = _initialize_phase_state(session_obj, active_phase, current_index)
        session_obj.phase_state_json = json.dumps(parsed, ensure_ascii=False)
        db.add(session_obj)
    return parsed


def phase_progress_snapshot(
    db: Session,
    session_obj: SessionModel,
    *,
    roleplay_state: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    phases, prefs = _scenario_phases_for_session(db, session_obj)
    if not phases:
        return {
            "active_phase_id": None,
            "active_phase_title": None,
            "phase_index": 0,
            "phase_count": 0,
            "score_count": 0,
            "target_score_count": 0,
            "remaining_score_count": 0,
            "metrics": [],
        }

    current_phase_id = str(prefs.get("scenario_phase_id") or "").strip()
    current_index = 0
    if current_phase_id:
        for index, phase in enumerate(phases):
            if str(phase.get("phase_id") or "").strip() == current_phase_id:
                current_index = index
                break

    active_phase = phases[current_index]
    phase_state = _ensure_phase_state_for_phase(db, session_obj, active_phase=active_phase, current_index=current_index)
    scores = phase_state.get("scores", {}) if isinstance(phase_state, dict) else {}
    targets = phase_state.get("targets", {}) if isinstance(phase_state, dict) else {}
    state = roleplay_state or build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=_scenario_title_for_session(db, session_obj),
        active_phase=active_phase,
        behavior_profile=_behavior_profile_for_session(db, session_obj),
    )
    relationship = state.get("relationship", {}) if isinstance(state, dict) else {}
    defaults = default_relationship_state()

    metrics: list[dict[str, Any]] = []
    for key, label in (
        ("trust", "Trust"),
        ("obedience", "Obedience"),
        ("resistance", "Resistance"),
        ("favor", "Favor"),
        ("strictness", "Strictness"),
        ("frustration", "Frustration"),
        ("attachment", "Attachment"),
    ):
        current_value = max(0, min(100, int(relationship.get(key) or defaults.get(key) or 0)))
        target_value = max(0, int(targets.get(key) or 0))
        score_value = max(0, min(target_value, int(scores.get(key) or 0)))
        remaining = max(0, target_value - score_value)
        metrics.append(
            {
                "key": key,
                "label": label,
                "current_value": current_value,
                "goal_value": target_value,
                "progress_value": score_value,
                "progress_total": max(1, target_value),
                "remaining": remaining,
                "goal_reached": target_value == 0 or remaining == 0,
            }
        )
    score_count = sum(1 for item in metrics if item["goal_reached"])
    target_score_count = len(metrics)
    remaining_score_count = max(0, target_score_count - score_count)
    return {
        "active_phase_id": str(active_phase.get("phase_id") or "").strip() or None,
        "active_phase_title": str(active_phase.get("title") or "").strip() or None,
        "phase_index": current_index + 1,
        "phase_count": len(phases),
        "score_count": score_count,
        "target_score_count": target_score_count,
        "remaining_score_count": remaining_score_count,
        "metrics": metrics,
    }


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
    normalized = str(event_type or "").strip().lower()
    behavior_profile = _behavior_profile_for_session(db, session_obj)
    progression_profile = progression_profile_from_behavior(behavior_profile)
    event_patch = ((progression_profile.get("events") or {}).get(normalized) or {}) if isinstance(progression_profile, dict) else {}
    relationship_deltas = event_patch.get("relationship_deltas") if isinstance(event_patch, dict) else {}
    if not isinstance(relationship_deltas, dict):
        relationship_deltas = {}

    phase_state = _ensure_phase_state_for_phase(db, session_obj, active_phase=current_phase, current_index=current_index)
    scores = dict(phase_state.get("scores") or {})
    targets = dict(phase_state.get("targets") or {})
    changed = False
    for key in _PHASE_SCORE_KEYS:
        target_value = max(0, int(targets.get(key) or 0))
        current_value = max(0, min(target_value, int(scores.get(key) or 0)))
        try:
            delta = int(relationship_deltas.get(key) or 0)
        except (TypeError, ValueError):
            delta = 0
        progress_delta = (-delta) if key == "resistance" else delta
        next_value = max(0, min(target_value, current_value + progress_delta))
        if next_value != current_value:
            scores[key] = next_value
            changed = True
    if changed:
        phase_state["scores"] = scores
        session_obj.phase_state_json = json.dumps(phase_state, ensure_ascii=False)
        db.add(session_obj)

    reached = sum(
        1
        for key in _PHASE_SCORE_KEYS
        if max(0, int(targets.get(key) or 0)) == 0 or max(0, int(scores.get(key) or 0)) >= max(0, int(targets.get(key) or 0))
    )
    prefs["scenario_phase_progress"] = reached

    if reached >= len(_PHASE_SCORE_KEYS) and current_index < len(phases) - 1:
        next_phase = phases[current_index + 1]
        next_phase_id = str(next_phase.get("phase_id") or "").strip()
        if next_phase_id:
            prefs["scenario_phase_id"] = next_phase_id
        prefs["scenario_phase_progress"] = 0
        profile.preferences_json = json.dumps(prefs, ensure_ascii=False)
        db.add(profile)
        next_state = _initialize_phase_state(session_obj, next_phase, current_index + 1)
        session_obj.phase_state_json = json.dumps(next_state, ensure_ascii=False)
        db.add(session_obj)
        return next_phase, f"Phase gewechselt: {str(next_phase.get('title') or next_phase_id or 'naechste Phase').strip()}"

    profile.preferences_json = json.dumps(prefs, ensure_ascii=False)
    db.add(profile)
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
