import json
from copy import deepcopy
from typing import Any


def _clamp_score(value: Any, default: int = 50) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def _list_of_text(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = str(raw or "").strip()
        if not text:
            continue
        items.append(text[:160])
        if len(items) >= limit:
            break
    return items


def _text(value: Any, default: str, limit: int = 240) -> str:
    text = str(value or "").strip()
    return text[:limit] if text else default


def default_relationship_state() -> dict[str, Any]:
    return {
        "trust": 55,
        "obedience": 50,
        "resistance": 20,
        "favor": 40,
        "strictness": 68,
        "frustration": 18,
        "attachment": 46,
        "control_level": "structured",
    }


def default_protocol_state() -> dict[str, Any]:
    return {
        "active_rules": [
            "Status klar und wahrheitsgemass melden",
            "Anweisungen ruhig und ohne Ausfluechte ausfuehren",
        ],
        "blocked_actions": [
            "Keine eigenmaechtigen Regelaufweichungen",
        ],
        "open_orders": [],
        "reward_focus": "Vertrauen durch saubere Ausfuehrung verdienen",
        "consequence_focus": "Bei Nachlaessigkeit folgen engere Kontrolle und Zusatzpflichten",
    }


def default_scene_state(scenario_title: str | None = None, active_phase: dict | None = None) -> dict[str, Any]:
    phase = active_phase or {}
    title = str(phase.get("title") or "").strip() or "Einstimmung"
    objective = str(phase.get("objective") or "").strip() or "Praesenz, Gehorsam und ruhige Fuehrung etablieren"
    pressure = str(phase.get("guidance") or "").strip() or "niedrig"
    return {
        "arc": str(scenario_title or "Keyholder Session").strip()[:120] or "Keyholder Session",
        "title": title[:120],
        "objective": objective[:240],
        "pressure": pressure[:200],
        "last_consequence": "",
        "next_beat": "Naechste klare Anweisung setzen und ruhige Compliance pruefen",
    }


def _normalize_relationship_state(value: Any) -> dict[str, Any]:
    base = default_relationship_state()
    if isinstance(value, dict):
        base["trust"] = _clamp_score(value.get("trust"), base["trust"])
        base["obedience"] = _clamp_score(value.get("obedience"), base["obedience"])
        base["resistance"] = _clamp_score(value.get("resistance"), base["resistance"])
        base["favor"] = _clamp_score(value.get("favor"), base["favor"])
        base["strictness"] = _clamp_score(value.get("strictness"), base["strictness"])
        base["frustration"] = _clamp_score(value.get("frustration"), base["frustration"])
        base["attachment"] = _clamp_score(value.get("attachment"), base["attachment"])
        base["control_level"] = _text(value.get("control_level"), base["control_level"], limit=80)
    return base


def _normalize_protocol_state(value: Any) -> dict[str, Any]:
    base = default_protocol_state()
    if isinstance(value, dict):
        base["active_rules"] = _list_of_text(value.get("active_rules")) or base["active_rules"]
        base["blocked_actions"] = _list_of_text(value.get("blocked_actions")) or base["blocked_actions"]
        base["open_orders"] = _list_of_text(value.get("open_orders"), limit=8)
        base["reward_focus"] = _text(value.get("reward_focus"), base["reward_focus"])
        base["consequence_focus"] = _text(value.get("consequence_focus"), base["consequence_focus"])
    return base


def _normalize_scene_state(value: Any, scenario_title: str | None = None, active_phase: dict | None = None) -> dict[str, Any]:
    base = default_scene_state(scenario_title=scenario_title, active_phase=active_phase)
    if isinstance(value, dict):
        base["arc"] = _text(value.get("arc"), base["arc"], limit=120)
        base["title"] = _text(value.get("title"), base["title"], limit=120)
        base["objective"] = _text(value.get("objective"), base["objective"], limit=240)
        base["pressure"] = _text(value.get("pressure"), base["pressure"], limit=200)
        base["last_consequence"] = _text(value.get("last_consequence"), base["last_consequence"], limit=240)
        base["next_beat"] = _text(value.get("next_beat"), base["next_beat"], limit=240)
    return base


def parse_json_dict(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_roleplay_state(
    relationship_json: str | None,
    protocol_json: str | None,
    scene_json: str | None,
    scenario_title: str | None = None,
    active_phase: dict | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        "relationship": _normalize_relationship_state(parse_json_dict(relationship_json)),
        "protocol": _normalize_protocol_state(parse_json_dict(protocol_json)),
        "scene": _normalize_scene_state(parse_json_dict(scene_json), scenario_title=scenario_title, active_phase=active_phase),
    }


def initialize_roleplay_state(
    scenario_title: str | None = None,
    active_phase: dict | None = None,
) -> dict[str, str]:
    state = build_roleplay_state(
        relationship_json=None,
        protocol_json=None,
        scene_json=None,
        scenario_title=scenario_title,
        active_phase=active_phase,
    )
    return {
        "relationship_state_json": json.dumps(state["relationship"], ensure_ascii=False),
        "protocol_state_json": json.dumps(state["protocol"], ensure_ascii=False),
        "scene_state_json": json.dumps(state["scene"], ensure_ascii=False),
    }


def merge_roleplay_state(
    current_state: dict[str, dict[str, Any]],
    patch: dict[str, Any],
    scenario_title: str | None = None,
    active_phase: dict | None = None,
) -> dict[str, dict[str, Any]]:
    merged = deepcopy(current_state)
    relationship_patch = patch.get("relationship")
    protocol_patch = patch.get("protocol")
    scene_patch = patch.get("scene")

    if isinstance(relationship_patch, dict):
        merged["relationship"].update(relationship_patch)
    if isinstance(protocol_patch, dict):
        merged["protocol"].update(protocol_patch)
    if isinstance(scene_patch, dict):
        merged["scene"].update(scene_patch)

    return {
        "relationship": _normalize_relationship_state(merged["relationship"]),
        "protocol": _normalize_protocol_state(merged["protocol"]),
        "scene": _normalize_scene_state(merged["scene"], scenario_title=scenario_title, active_phase=active_phase),
    }


def serialize_roleplay_state(state: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        "relationship_state_json": json.dumps(state["relationship"], ensure_ascii=False),
        "protocol_state_json": json.dumps(state["protocol"], ensure_ascii=False),
        "scene_state_json": json.dumps(state["scene"], ensure_ascii=False),
    }


def summarize_roleplay_state_changes(previous_state: dict[str, dict[str, Any]], next_state: dict[str, dict[str, Any]]) -> str:
    changes: list[str] = []
    previous_scene = previous_state.get("scene", {})
    next_scene = next_state.get("scene", {})
    previous_relationship = previous_state.get("relationship", {})
    next_relationship = next_state.get("relationship", {})

    if previous_scene.get("title") != next_scene.get("title"):
        changes.append(f"Szene: {next_scene.get('title')}")
    if previous_scene.get("objective") != next_scene.get("objective"):
        changes.append(f"Ziel: {next_scene.get('objective')}")
    if previous_scene.get("last_consequence") != next_scene.get("last_consequence") and next_scene.get("last_consequence"):
        changes.append(f"Konsequenz: {next_scene.get('last_consequence')}")

    for key in ("trust", "obedience", "resistance", "strictness"):
        if previous_relationship.get(key) != next_relationship.get(key):
            changes.append(f"{key}={next_relationship.get(key)}")

    if previous_relationship.get("control_level") != next_relationship.get("control_level"):
        changes.append(f"Kontrollmodus: {next_relationship.get('control_level')}")

    if not changes:
        return "Roleplay-State aktualisiert."
    return "Roleplay-State aktualisiert: " + "; ".join(changes[:6])
