import json
import re
from typing import Any

from app.models.persona import Persona
from app.models.player_profile import PlayerProfile

BUILTIN_TOY_PRESETS = {
    "tease_ramp": {
        "key": "tease_ramp",
        "name": "Tease Ramp",
        "command": "pattern",
        "pattern": "builtin:tease_ramp",
        "interval": 220,
        "owner_type": "builtin",
        "is_builtin": True,
    },
    "strict_pulse": {
        "key": "strict_pulse",
        "name": "Strict Pulse",
        "command": "pattern",
        "pattern": "builtin:strict_pulse",
        "interval": 160,
        "owner_type": "builtin",
        "is_builtin": True,
    },
    "wave_ladder": {
        "key": "wave_ladder",
        "name": "Wave Ladder",
        "command": "pattern",
        "pattern": "builtin:wave_ladder",
        "interval": 210,
        "owner_type": "builtin",
        "is_builtin": True,
    },
    "deny_spikes": {
        "key": "deny_spikes",
        "name": "Deny Spikes",
        "command": "pattern",
        "pattern": "builtin:deny_spikes",
        "interval": 150,
        "owner_type": "builtin",
        "is_builtin": True,
    },
}

TOY_PRESET_COMMANDS = {"vibrate", "pulse", "wave", "preset", "pattern"}


def _slugify(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return text[:80] or "preset"


def _load_player_preferences(profile: PlayerProfile | None) -> dict[str, Any]:
    if profile is None or not profile.preferences_json:
        return {}
    try:
        value = json.loads(profile.preferences_json)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _dump_player_preferences(profile: PlayerProfile, prefs: dict[str, Any]) -> None:
    profile.preferences_json = json.dumps(prefs, ensure_ascii=False)


def _load_persona_behavior(persona: Persona | None) -> dict[str, Any]:
    if persona is None or not persona.behavior_profile_json:
        return {}
    try:
        value = json.loads(persona.behavior_profile_json)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _dump_persona_behavior(persona: Persona, behavior: dict[str, Any]) -> None:
    persona.behavior_profile_json = json.dumps(behavior, ensure_ascii=False)


def normalize_toy_preset(value: Any, *, owner_type: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or "").strip()[:120]
    if not name:
        return None
    command = str(value.get("command") or "pattern").strip().lower()
    if command not in TOY_PRESET_COMMANDS:
        command = "pattern"
    key = _slugify(value.get("key") or name)
    preset = {
        "key": key,
        "name": name,
        "command": command,
        "owner_type": owner_type,
        "is_builtin": False,
    }
    if command in {"vibrate", "pulse", "wave"}:
        intensity = max(1, min(20, int(value.get("intensity") or 8)))
        duration_seconds = max(1, min(120, int(value.get("duration_seconds") or 20)))
        pause_seconds = max(0, min(60, int(value.get("pause_seconds") or 0)))
        loops = max(1, min(10, int(value.get("loops") or 1)))
        preset.update({
            "intensity": intensity,
            "duration_seconds": duration_seconds,
            "pause_seconds": pause_seconds,
            "loops": loops,
        })
    elif command == "preset":
        target = str(value.get("preset") or "").strip().lower()
        if target not in BUILTIN_TOY_PRESETS:
            return None
        duration_seconds = max(1, min(120, int(value.get("duration_seconds") or 20)))
        pause_seconds = max(0, min(60, int(value.get("pause_seconds") or 0)))
        loops = max(1, min(10, int(value.get("loops") or 1)))
        preset.update({
            "preset": target,
            "duration_seconds": duration_seconds,
            "pause_seconds": pause_seconds,
            "loops": loops,
        })
    else:
        pattern = str(value.get("pattern") or "").strip()
        if not pattern:
            return None
        duration_seconds = max(1, min(180, int(value.get("duration_seconds") or 20)))
        interval = max(100, min(1000, int(value.get("interval") or 180)))
        pause_seconds = max(0, min(60, int(value.get("pause_seconds") or 0)))
        loops = max(1, min(10, int(value.get("loops") or 1)))
        preset.update({
            "pattern": pattern[:240],
            "interval": interval,
            "duration_seconds": duration_seconds,
            "pause_seconds": pause_seconds,
            "loops": loops,
        })
    return preset


def _normalize_toy_preset_list(raw: Any, *, owner_type: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw:
        normalized = normalize_toy_preset(entry, owner_type=owner_type)
        if not normalized:
            continue
        key = normalized["key"]
        if key in seen:
            continue
        seen.add(key)
        items.append(normalized)
    return items[:24]


def get_player_toy_presets(profile: PlayerProfile | None) -> list[dict[str, Any]]:
    prefs = _load_player_preferences(profile)
    toys = prefs.get("toys") if isinstance(prefs.get("toys"), dict) else {}
    return _normalize_toy_preset_list(toys.get("custom_presets"), owner_type="wearer")


def save_player_toy_preset(profile: PlayerProfile, payload: dict[str, Any]) -> list[dict[str, Any]]:
    preset = normalize_toy_preset(payload, owner_type="wearer")
    if not preset:
        raise ValueError("Invalid toy preset payload")
    prefs = _load_player_preferences(profile)
    toys = prefs.get("toys") if isinstance(prefs.get("toys"), dict) else {}
    presets = [item for item in _normalize_toy_preset_list(toys.get("custom_presets"), owner_type="wearer") if item["key"] != preset["key"]]
    presets.append(preset)
    toys["custom_presets"] = presets
    prefs["toys"] = toys
    _dump_player_preferences(profile, prefs)
    return presets


def delete_player_toy_preset(profile: PlayerProfile, preset_key: str) -> list[dict[str, Any]]:
    key = _slugify(preset_key)
    prefs = _load_player_preferences(profile)
    toys = prefs.get("toys") if isinstance(prefs.get("toys"), dict) else {}
    presets = [item for item in _normalize_toy_preset_list(toys.get("custom_presets"), owner_type="wearer") if item["key"] != key]
    toys["custom_presets"] = presets
    prefs["toys"] = toys
    _dump_player_preferences(profile, prefs)
    return presets


def get_persona_toy_presets(persona: Persona | None) -> list[dict[str, Any]]:
    behavior = _load_persona_behavior(persona)
    return _normalize_toy_preset_list(behavior.get("toy_presets"), owner_type="persona")


def save_persona_toy_preset(persona: Persona, payload: dict[str, Any]) -> list[dict[str, Any]]:
    preset = normalize_toy_preset(payload, owner_type="persona")
    if not preset:
        raise ValueError("Invalid toy preset payload")
    behavior = _load_persona_behavior(persona)
    presets = [item for item in _normalize_toy_preset_list(behavior.get("toy_presets"), owner_type="persona") if item["key"] != preset["key"]]
    presets.append(preset)
    behavior["toy_presets"] = presets
    _dump_persona_behavior(persona, behavior)
    return presets


def delete_persona_toy_preset(persona: Persona, preset_key: str) -> list[dict[str, Any]]:
    key = _slugify(preset_key)
    behavior = _load_persona_behavior(persona)
    presets = [item for item in _normalize_toy_preset_list(behavior.get("toy_presets"), owner_type="persona") if item["key"] != key]
    behavior["toy_presets"] = presets
    _dump_persona_behavior(persona, behavior)
    return presets


def build_toy_preset_library(*, profile: PlayerProfile | None, persona: Persona | None) -> dict[str, Any]:
    wearer_presets = get_player_toy_presets(profile)
    persona_presets = get_persona_toy_presets(persona)
    combined = {key: value for key, value in BUILTIN_TOY_PRESETS.items()}
    for entry in wearer_presets + persona_presets:
        combined[entry["key"]] = entry
    return {
        "builtin": list(BUILTIN_TOY_PRESETS.values()),
        "wearer": wearer_presets,
        "persona": persona_presets,
        "combined": list(combined.values()),
    }
