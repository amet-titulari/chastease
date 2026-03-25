from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.models.persona import Persona
from app.models.scenario import Scenario
from sqlalchemy.orm import Session


DEFAULT_DIRECTOR_PROFILE = {
    "task_eagerness": "high",
    "state_update_aggressiveness": "balanced",
    "consequence_style": "balanced",
    "scene_visibility": "contextual",
}

DEFAULT_REMINDER_PROFILE = {
    "opening_soft": "Ruhig bleiben.",
    "opening_firm": "Haltung halten.",
    "opening_default": "Bleib sauber im Protokoll.",
    "max_sentences": 3,
    "mention_time_hint": True,
}

DEFAULT_PROGRESSION_PROFILE = {
    "events": {
        "task_completed": {
            "relationship_deltas": {"trust": 2, "obedience": 2, "favor": 1, "resistance": -1},
            "scene": {
                "pressure": "niedrig",
                "last_consequence": "Saubere Pflichterfuellung wurde positiv vermerkt.",
                "next_beat": "Naechste Anweisung setzen und die ruhige Compliance halten.",
            },
        },
        "task_failed": {
            "relationship_deltas": {"trust": -2, "obedience": -3, "resistance": 2, "strictness": 2, "frustration": 2},
            "scene": {
                "pressure": "mittel",
                "last_consequence": "Pflicht verfehlt; Kontrolle und Nachfassen wurden verschaerft.",
                "next_beat": "Konsequenz umsetzen und erneute Compliance pruefen.",
            },
        },
        "task_overdue": {
            "relationship_deltas": {"trust": -2, "obedience": -3, "resistance": 2, "strictness": 2, "frustration": 2},
            "scene": {
                "pressure": "mittel",
                "last_consequence": "Pflicht ueberfaellig; Kontrolle und Nachfassen wurden verschaerft.",
                "next_beat": "Konsequenz umsetzen und erneute Compliance pruefen.",
            },
        },
        "verification_confirmed": {
            "relationship_deltas": {"trust": 3, "obedience": 2, "favor": 1, "resistance": -1},
            "scene": {
                "pressure": "niedrig",
                "last_consequence": "Nachweis sauber erbracht und positiv registriert.",
                "next_beat": "Die naechste Pflicht darf auf dieser Verlaesslichkeit aufbauen.",
            },
        },
        "verification_suspicious": {
            "relationship_deltas": {"trust": -2, "obedience": -2, "resistance": 1, "strictness": 2, "frustration": 2},
            "scene": {
                "pressure": "mittel",
                "last_consequence": "Nachweis war nicht ueberzeugend; Kontrolle wurde enger.",
                "next_beat": "Klaren Nachweis nachfordern und die Ausfuehrung enger fuehren.",
            },
        },
        "game_report_success": {
            "relationship_deltas": {"trust": 3, "obedience": 3, "favor": 2, "resistance": -1, "attachment": 1},
            "scene": {
                "pressure": "niedrig",
                "last_consequence": "Spiel sauber gemeistert; Fuehrung und Vertrauen wurden bestaetigt.",
                "next_beat": "Die naechste Szene kann auf dieser Disziplin aufbauen.",
            },
        },
        "game_report_failure": {
            "relationship_deltas": {"trust": -2, "obedience": -2, "resistance": 1, "strictness": 2, "frustration": 3},
            "scene": {
                "pressure": "hoch",
                "last_consequence": "Spiel schwach abgeschlossen; Nachschulung und engere Kontrolle stehen an.",
                "next_beat": "Fehlerbild klar benennen und die naechste Uebung straffer fuehren.",
            },
        },
        "game_report_mixed": {
            "relationship_deltas": {"trust": 1, "obedience": 1, "strictness": 1, "frustration": 1},
            "scene": {
                "pressure": "mittel",
                "last_consequence": "Spiel mit gemischtem Ergebnis; Fuehrung bleibt praesent und nachschaerfend.",
                "next_beat": "Schwaechen nachziehen und anschliessend wieder stabile Compliance verlangen.",
            },
        },
    }
}


def _deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def parse_behavior_profile(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def dumps_behavior_profile(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    return json.dumps(value, ensure_ascii=False)


def merge_behavior_profiles(*profiles: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for profile in profiles:
        if isinstance(profile, dict) and profile:
            merged = _deep_merge_dicts(merged, profile)
    return merged


def behavior_profile_from_entities(
    *,
    persona: Persona | None = None,
    scenario: Scenario | None = None,
) -> dict[str, Any]:
    return merge_behavior_profiles(
        parse_behavior_profile(getattr(persona, "behavior_profile_json", None)),
        parse_behavior_profile(getattr(scenario, "behavior_profile_json", None)),
    )


def behavior_profile_from_scenario_key(db: Session, scenario_key: str | None) -> dict[str, Any]:
    key = str(scenario_key or "").strip()
    if not key:
        return {}
    row = db.query(Scenario).filter(Scenario.key == key).first()
    if row is not None:
        return parse_behavior_profile(row.behavior_profile_json)
    try:
        from app.routers.scenarios import SCENARIO_PRESETS

        preset = next((item for item in SCENARIO_PRESETS if str(item.get("key") or "").strip() == key), None)
        if isinstance(preset, dict):
            raw = preset.get("behavior_profile")
            return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}
    return {}


def roleplay_defaults_from_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    value = profile.get("roleplay_defaults")
    return value if isinstance(value, dict) else {}


def progression_profile_from_behavior(profile: dict[str, Any] | None) -> dict[str, Any]:
    base = deepcopy(DEFAULT_PROGRESSION_PROFILE)
    if not isinstance(profile, dict):
        return base
    value = profile.get("progression")
    if isinstance(value, dict):
        return _deep_merge_dicts(base, value)
    return base


def reminder_profile_from_behavior(profile: dict[str, Any] | None) -> dict[str, Any]:
    base = deepcopy(DEFAULT_REMINDER_PROFILE)
    if not isinstance(profile, dict):
        return base
    value = profile.get("reminder")
    if isinstance(value, dict):
        return _deep_merge_dicts(base, value)
    return base


def director_profile_from_behavior(profile: dict[str, Any] | None) -> dict[str, Any]:
    base = deepcopy(DEFAULT_DIRECTOR_PROFILE)
    if not isinstance(profile, dict):
        return base
    value = profile.get("director")
    if isinstance(value, dict):
        return _deep_merge_dicts(base, value)
    return base
