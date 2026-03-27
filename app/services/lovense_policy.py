import json
from typing import Any

from app.models.player_profile import PlayerProfile

LOVENSE_POLICY_COMMANDS = ("vibrate", "pulse", "wave", "preset")

DEFAULT_LOVENSE_POLICY = {
    "min_intensity": None,
    "max_intensity": None,
    "min_step_duration_seconds": None,
    "max_step_duration_seconds": None,
    "min_pause_seconds": None,
    "max_pause_seconds": None,
    "max_plan_duration_seconds": None,
    "max_plan_steps": None,
    "allow_presets": True,
    "allow_append_mode": True,
    "allowed_commands": {command: True for command in LOVENSE_POLICY_COMMANDS},
}


def _load_profile_preferences(profile: PlayerProfile | None) -> dict[str, Any]:
    if profile is None or not profile.preferences_json:
        return {}
    try:
        value = json.loads(profile.preferences_json)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _dump_profile_preferences(profile: PlayerProfile, prefs: dict[str, Any]) -> None:
    profile.preferences_json = json.dumps(prefs, ensure_ascii=False)


def _parse_optional_int(value: Any, *, minimum: int, maximum: int) -> int | None:
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"value must be between {minimum} and {maximum}")
    return parsed


def _parse_bool(value: Any, *, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_lovense_policy(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    allowed_source = source.get("allowed_commands") if isinstance(source.get("allowed_commands"), dict) else {}
    policy = {
        "min_intensity": _parse_optional_int(source.get("min_intensity"), minimum=1, maximum=20),
        "max_intensity": _parse_optional_int(source.get("max_intensity"), minimum=1, maximum=20),
        "min_step_duration_seconds": _parse_optional_int(source.get("min_step_duration_seconds"), minimum=1, maximum=180),
        "max_step_duration_seconds": _parse_optional_int(source.get("max_step_duration_seconds"), minimum=1, maximum=180),
        "min_pause_seconds": _parse_optional_int(source.get("min_pause_seconds"), minimum=0, maximum=300),
        "max_pause_seconds": _parse_optional_int(source.get("max_pause_seconds"), minimum=0, maximum=300),
        "max_plan_duration_seconds": _parse_optional_int(source.get("max_plan_duration_seconds"), minimum=1, maximum=900),
        "max_plan_steps": _parse_optional_int(source.get("max_plan_steps"), minimum=1, maximum=24),
        "allow_presets": _parse_bool(source.get("allow_presets"), default=True),
        "allow_append_mode": _parse_bool(source.get("allow_append_mode"), default=True),
        "allowed_commands": {
            command: _parse_bool(allowed_source.get(command), default=True)
            for command in LOVENSE_POLICY_COMMANDS
        },
    }
    if policy["min_intensity"] is not None and policy["max_intensity"] is not None and policy["min_intensity"] > policy["max_intensity"]:
        raise ValueError("min_intensity must be <= max_intensity")
    if (
        policy["min_step_duration_seconds"] is not None
        and policy["max_step_duration_seconds"] is not None
        and policy["min_step_duration_seconds"] > policy["max_step_duration_seconds"]
    ):
        raise ValueError("min_step_duration_seconds must be <= max_step_duration_seconds")
    if (
        policy["min_pause_seconds"] is not None
        and policy["max_pause_seconds"] is not None
        and policy["min_pause_seconds"] > policy["max_pause_seconds"]
    ):
        raise ValueError("min_pause_seconds must be <= max_pause_seconds")
    return policy


def get_lovense_policy_for_profile(profile: PlayerProfile | None) -> dict[str, Any]:
    prefs = _load_profile_preferences(profile)
    toys = prefs.get("toys") if isinstance(prefs.get("toys"), dict) else {}
    return normalize_lovense_policy(toys.get("lovense_policy"))


def save_lovense_policy_for_profile(profile: PlayerProfile, policy_payload: dict[str, Any]) -> dict[str, Any]:
    policy = normalize_lovense_policy(policy_payload)
    prefs = _load_profile_preferences(profile)
    toys = prefs.get("toys") if isinstance(prefs.get("toys"), dict) else {}
    toys["lovense_policy"] = policy
    prefs["toys"] = toys
    _dump_profile_preferences(profile, prefs)
    return policy


def _clamp_with_policy(value: Any, *, minimum: int | None, maximum: int | None, fallback: int | None = None) -> int | None:
    if value in (None, ""):
        return fallback
    parsed = int(value)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def apply_lovense_policy_to_control_action(action: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any] | None:
    policy = normalize_lovense_policy(policy)
    if not isinstance(action, dict):
        return None
    command = str(action.get("command") or "").strip().lower()
    if command == "stop":
        return {"type": "lovense_control", "command": "stop"}
    if command not in LOVENSE_POLICY_COMMANDS:
        return None
    if not policy["allowed_commands"].get(command, True):
        return None
    if command == "preset" and not policy.get("allow_presets", True):
        return None

    sanitized = dict(action)
    if command in {"vibrate", "pulse", "wave"}:
        sanitized["intensity"] = _clamp_with_policy(
            sanitized.get("intensity"),
            minimum=policy.get("min_intensity"),
            maximum=policy.get("max_intensity"),
            fallback=policy.get("min_intensity"),
        )
    if command in {"vibrate", "pulse", "wave", "preset"}:
        sanitized["duration_seconds"] = _clamp_with_policy(
            sanitized.get("duration_seconds"),
            minimum=policy.get("min_step_duration_seconds"),
            maximum=policy.get("max_step_duration_seconds"),
            fallback=policy.get("min_step_duration_seconds"),
        )
    if sanitized.get("pause_seconds") is not None or sanitized.get("loops") not in (None, "", 1, "1"):
        sanitized["pause_seconds"] = _clamp_with_policy(
            sanitized.get("pause_seconds"),
            minimum=policy.get("min_pause_seconds"),
            maximum=policy.get("max_pause_seconds"),
            fallback=policy.get("min_pause_seconds", 0),
        )
    return {key: value for key, value in sanitized.items() if value is not None}


def _apply_duration_budget(
    steps: list[dict[str, Any]],
    *,
    max_plan_duration_seconds: int | None,
    min_step_duration_seconds: int | None,
    min_pause_seconds: int | None,
) -> list[dict[str, Any]]:
    if max_plan_duration_seconds is None:
        return steps
    remaining = int(max_plan_duration_seconds)
    bounded: list[dict[str, Any]] = []
    for step in steps:
        command = str(step.get("command") or "").strip().lower()
        if command == "stop":
            bounded.append(step)
            continue
        duration = int(step.get("duration_seconds") or 0)
        if duration <= 0:
            continue
        minimum = min_pause_seconds if command == "pause" else min_step_duration_seconds
        if remaining <= 0:
            break
        next_duration = min(duration, remaining)
        if minimum is not None and next_duration < minimum:
            break
        next_step = dict(step)
        next_step["duration_seconds"] = next_duration
        bounded.append(next_step)
        remaining -= next_duration
    return bounded


def apply_lovense_policy_to_session_plan(action: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any] | None:
    policy = normalize_lovense_policy(policy)
    if not isinstance(action, dict):
        return None
    steps_raw = action.get("steps") if isinstance(action.get("steps"), list) else []
    sanitized_steps: list[dict[str, Any]] = []
    for raw_step in steps_raw:
        if not isinstance(raw_step, dict):
            continue
        command = str(raw_step.get("command") or "").strip().lower()
        if command == "stop":
            sanitized_steps.append({"command": "stop"})
            continue
        if command == "pause":
            pause_duration = _clamp_with_policy(
                raw_step.get("duration_seconds"),
                minimum=policy.get("min_pause_seconds"),
                maximum=policy.get("max_pause_seconds"),
                fallback=policy.get("min_pause_seconds"),
            )
            if pause_duration is None:
                continue
            sanitized_steps.append({"command": "pause", "duration_seconds": pause_duration})
            continue
        if command not in LOVENSE_POLICY_COMMANDS:
            continue
        if not policy["allowed_commands"].get(command, True):
            continue
        if command == "preset" and not policy.get("allow_presets", True):
            continue
        step = dict(raw_step)
        if command in {"vibrate", "pulse", "wave"}:
            step["intensity"] = _clamp_with_policy(
                step.get("intensity"),
                minimum=policy.get("min_intensity"),
                maximum=policy.get("max_intensity"),
                fallback=policy.get("min_intensity"),
            )
        step["duration_seconds"] = _clamp_with_policy(
            step.get("duration_seconds"),
            minimum=policy.get("min_step_duration_seconds"),
            maximum=policy.get("max_step_duration_seconds"),
            fallback=policy.get("min_step_duration_seconds"),
        )
        sanitized_steps.append({key: value for key, value in step.items() if value is not None})

    max_steps = policy.get("max_plan_steps")
    if max_steps is not None:
        sanitized_steps = sanitized_steps[: int(max_steps)]
    sanitized_steps = _apply_duration_budget(
        sanitized_steps,
        max_plan_duration_seconds=policy.get("max_plan_duration_seconds"),
        min_step_duration_seconds=policy.get("min_step_duration_seconds"),
        min_pause_seconds=policy.get("min_pause_seconds"),
    )
    if not sanitized_steps:
        return None
    sanitized = dict(action)
    sanitized["steps"] = sanitized_steps
    if not policy.get("allow_append_mode", True):
        sanitized["mode"] = "replace"
    return sanitized
