from typing import Any


TOY_PROVIDER_CHOICES = ("none", "lovense", "ttlock", "custom")
TOY_PRESET_CHOICES = ("", "tease_ramp", "strict_pulse", "wave_ladder", "deny_spikes")

DEFAULT_TOY_PROFILE = {
    "provider": "none",
    "enabled": False,
    "preferred_toy_name": "",
    "preferred_toy_id": "",
    "preferred_preset": "",
    "default_intensity": 8,
    "default_duration_seconds": 20,
    "default_pause_seconds": 5,
    "default_loops": 1,
}

_MANAGED_TOY_PROFILE_KEYS = set(DEFAULT_TOY_PROFILE.keys())


def _parse_optional_int(value: Any, *, minimum: int, maximum: int, fallback: int) -> int:
    if value in (None, ""):
        return fallback
    parsed = int(value)
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _parse_bool(value: Any, *, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def normalize_toy_profile(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    provider = str(source.get("provider") or DEFAULT_TOY_PROFILE["provider"]).strip().lower()
    if provider not in TOY_PROVIDER_CHOICES:
        provider = DEFAULT_TOY_PROFILE["provider"]
    preferred_preset = str(source.get("preferred_preset") or "").strip().lower()
    if preferred_preset not in TOY_PRESET_CHOICES:
        preferred_preset = ""
    return {
        "provider": provider,
        "enabled": _parse_bool(source.get("enabled"), default=DEFAULT_TOY_PROFILE["enabled"]),
        "preferred_toy_name": str(source.get("preferred_toy_name") or "").strip()[:120],
        "preferred_toy_id": str(source.get("preferred_toy_id") or "").strip()[:160],
        "preferred_preset": preferred_preset,
        "default_intensity": _parse_optional_int(
            source.get("default_intensity"),
            minimum=1,
            maximum=20,
            fallback=DEFAULT_TOY_PROFILE["default_intensity"],
        ),
        "default_duration_seconds": _parse_optional_int(
            source.get("default_duration_seconds"),
            minimum=1,
            maximum=300,
            fallback=DEFAULT_TOY_PROFILE["default_duration_seconds"],
        ),
        "default_pause_seconds": _parse_optional_int(
            source.get("default_pause_seconds"),
            minimum=0,
            maximum=300,
            fallback=DEFAULT_TOY_PROFILE["default_pause_seconds"],
        ),
        "default_loops": _parse_optional_int(
            source.get("default_loops"),
            minimum=1,
            maximum=20,
            fallback=DEFAULT_TOY_PROFILE["default_loops"],
        ),
    }


def get_toy_profile_from_preferences(prefs: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(prefs, dict):
        return dict(DEFAULT_TOY_PROFILE)
    toys = prefs.get("toys") if isinstance(prefs.get("toys"), dict) else {}
    return normalize_toy_profile(toys)


def merge_toy_profile(existing_toys: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing_toys) if isinstance(existing_toys, dict) else {}
    normalized = normalize_toy_profile(payload)
    for key in list(merged.keys()):
        if key in _MANAGED_TOY_PROFILE_KEYS:
            merged.pop(key, None)
    merged.update(normalized)
    return merged
