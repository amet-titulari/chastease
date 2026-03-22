import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel
from app.services.roleplay_state import (
    build_roleplay_state,
    merge_roleplay_state,
    serialize_roleplay_state,
    summarize_roleplay_state_changes,
)


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
    task_title: str | None = None,
) -> dict[str, Any] | None:
    relationship = current_state.get("relationship", {})
    protocol = current_state.get("protocol", {})

    if event_type == "task_completed":
        relationship_patch = _relationship_patch(
            relationship,
            {"trust": 2, "obedience": 2, "favor": 1, "resistance": -1},
        )
        patch: dict[str, Any] = {
            "relationship": relationship_patch,
            "scene": {
                "pressure": "niedrig",
                "last_consequence": "Saubere Pflichterfuellung wurde positiv vermerkt.",
                "next_beat": "Naechste Anweisung setzen und die ruhige Compliance halten.",
            },
        }
        next_orders = _trim_open_orders(protocol, task_title)
        if next_orders is not None:
            patch["protocol"] = {"open_orders": next_orders}
        return patch

    if event_type in {"task_failed", "task_overdue"}:
        relationship_patch = _relationship_patch(
            relationship,
            {"trust": -2, "obedience": -3, "resistance": 2, "strictness": 2, "frustration": 2},
        )
        label = "Pflicht verfehlt" if event_type == "task_failed" else "Pflicht ueberfaellig"
        patch = {
            "relationship": relationship_patch,
            "scene": {
                "pressure": "mittel",
                "last_consequence": f"{label}; Kontrolle und Nachfassen wurden verschaerft.",
                "next_beat": "Konsequenz umsetzen und erneute Compliance pruefen.",
            },
        }
        next_orders = _trim_open_orders(protocol, task_title)
        if next_orders is not None:
            patch["protocol"] = {"open_orders": next_orders}
        return patch

    return None


def _patch_for_verification_event(
    current_state: dict[str, dict[str, Any]],
    *,
    status: str,
) -> dict[str, Any] | None:
    relationship = current_state.get("relationship", {})
    normalized = str(status or "").strip().lower()
    if normalized == "confirmed":
        return {
            "relationship": _relationship_patch(
                relationship,
                {"trust": 3, "obedience": 2, "favor": 1, "resistance": -1},
            ),
            "scene": {
                "pressure": "niedrig",
                "last_consequence": "Nachweis sauber erbracht und positiv registriert.",
                "next_beat": "Die naechste Pflicht darf auf dieser Verlaesslichkeit aufbauen.",
            },
        }
    if normalized == "suspicious":
        return {
            "relationship": _relationship_patch(
                relationship,
                {"trust": -2, "obedience": -2, "resistance": 1, "strictness": 2, "frustration": 2},
            ),
            "scene": {
                "pressure": "mittel",
                "last_consequence": "Nachweis war nicht ueberzeugend; Kontrolle wurde enger.",
                "next_beat": "Klaren Nachweis nachfordern und die Ausfuehrung enger fuehren.",
            },
        }
    return None


def _patch_for_game_report(
    current_state: dict[str, dict[str, Any]],
    *,
    passed_steps: int,
    failed_steps: int,
    miss_count: int,
    scheduled_steps: int,
) -> dict[str, Any] | None:
    relationship = current_state.get("relationship", {})
    total = max(1, int(scheduled_steps or 0))
    passed = max(0, int(passed_steps or 0))
    failed = max(0, int(failed_steps or 0))
    misses = max(0, int(miss_count or 0))
    ratio = passed / total

    if ratio >= 0.8 and failed == 0 and misses <= 1:
        return {
            "relationship": _relationship_patch(
                relationship,
                {"trust": 3, "obedience": 3, "favor": 2, "resistance": -1, "attachment": 1},
            ),
            "scene": {
                "pressure": "niedrig",
                "last_consequence": "Spiel sauber gemeistert; Fuehrung und Vertrauen wurden bestaetigt.",
                "next_beat": "Die naechste Szene kann auf dieser Disziplin aufbauen.",
            },
        }

    if ratio <= 0.4 or failed > passed or misses >= 3:
        return {
            "relationship": _relationship_patch(
                relationship,
                {"trust": -2, "obedience": -2, "resistance": 1, "strictness": 2, "frustration": 3},
            ),
            "scene": {
                "pressure": "hoch",
                "last_consequence": "Spiel schwach abgeschlossen; Nachschulung und engere Kontrolle stehen an.",
                "next_beat": "Fehlerbild klar benennen und die naechste Uebung straffer fuehren.",
            },
        }

    return {
        "relationship": _relationship_patch(
            relationship,
            {"trust": 1, "obedience": 1, "strictness": 1, "frustration": 1},
        ),
        "scene": {
            "pressure": "mittel",
            "last_consequence": "Spiel mit gemischtem Ergebnis; Fuehrung bleibt praesent und nachschaerfend.",
            "next_beat": "Schwaechen nachziehen und anschliessend wieder stabile Compliance verlangen.",
        },
    }


def roleplay_patch_for_event(
    current_state: dict[str, dict[str, Any]],
    *,
    event_type: str,
    **kwargs: Any,
) -> dict[str, Any] | None:
    normalized = str(event_type or "").strip().lower()
    if normalized in {"task_completed", "task_failed", "task_overdue"}:
        return _patch_for_task_event(current_state, event_type=normalized, task_title=kwargs.get("task_title"))
    if normalized in {"verification_confirmed", "verification_suspicious"}:
        status = "confirmed" if normalized.endswith("confirmed") else "suspicious"
        return _patch_for_verification_event(current_state, status=status)
    if normalized == "game_report":
        return _patch_for_game_report(
            current_state,
            passed_steps=int(kwargs.get("passed_steps") or 0),
            failed_steps=int(kwargs.get("failed_steps") or 0),
            miss_count=int(kwargs.get("miss_count") or 0),
            scheduled_steps=int(kwargs.get("scheduled_steps") or 0),
        )
    return None


def advance_roleplay_state_from_event(
    db: Session,
    session_obj: SessionModel,
    *,
    event_type: str,
    message_type: str = "session_state_updated",
    **kwargs: Any,
) -> bool:
    scenario_title = _scenario_title_for_session(db, session_obj)
    current_state = build_roleplay_state(
        relationship_json=session_obj.relationship_state_json,
        protocol_json=session_obj.protocol_state_json,
        scene_json=session_obj.scene_state_json,
        scenario_title=scenario_title,
        active_phase=None,
    )
    patch = roleplay_patch_for_event(current_state, event_type=event_type, **kwargs)
    if not patch:
        return False

    next_state = merge_roleplay_state(
        current_state=current_state,
        patch=patch,
        scenario_title=scenario_title,
        active_phase=None,
    )
    if next_state == current_state:
        return False

    serialized = serialize_roleplay_state(next_state)
    session_obj.relationship_state_json = serialized["relationship_state_json"]
    session_obj.protocol_state_json = serialized["protocol_state_json"]
    session_obj.scene_state_json = serialized["scene_state_json"]
    db.add(session_obj)
    db.add(
        Message(
            session_id=session_obj.id,
            role="system",
            message_type=message_type,
            content=summarize_roleplay_state_changes(current_state, next_state),
        )
    )
    return True
