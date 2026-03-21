from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.ai_gateway import get_ai_gateway


DEFAULT_CONTRACT_PREFERENCES: dict[str, Any] = {
    "keyholder_title": "Keyholder",
    "wearer_title": "Wearer",
    "goal": "Einvernehmliche Keuschhaltung mit klarer Fuehrung, Verbindlichkeit und lustvoller Enthaltsamkeit.",
    "method": "",
    "wearing_schedule": "dauerhaft, soweit Gesundheit und Alltag es sicher erlauben",
    "touch_rules": "Genitalberuehrung, aktive Stimulation und gezielte Erregungssteigerung nur mit ausdruecklicher Erlaubnis.",
    "orgasm_rules": "Orgasmen, ruined orgasms, edging und vergleichbare sexuelle Freigaben nur nach ausdruecklicher Freigabe.",
    "reward_policy": "Belohnungen koennen kontrollierte Tease-Sessions, Lob, besondere Aufmerksamkeit oder begrenzte Freigaben sein.",
    "termination_policy": "Beide Parteien koennen die Vereinbarung jederzeit beenden; Safety und Gesundheit gehen immer vor.",
}


def default_contract_preferences() -> dict[str, Any]:
    return deepcopy(DEFAULT_CONTRACT_PREFERENCES)


def normalize_contract_preferences(raw: Any) -> dict[str, Any]:
    base = default_contract_preferences()
    if not isinstance(raw, dict):
        return base
    for key in base.keys():
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        base[key] = text[:4000]
    return base


def build_contract_context(
    *,
    keyholder_name: str,
    wearer_name: str,
    min_duration_seconds: int,
    max_duration_seconds: int | None,
    contract_preferences: dict[str, Any] | None = None,
    hard_limits: list[str] | None = None,
    scenario_title: str | None = None,
    seal_number: str | None = None,
    hygiene_opening_max_duration_seconds: int | None = None,
    reference_at: datetime | None = None,
    selected_duration_seconds: int | None = None,
) -> dict[str, Any]:
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _fmt(value: datetime | None) -> str | None:
        if value is None:
            return None
        return _as_utc(value).strftime("%d.%m.%Y %H:%M UTC")

    prefs = normalize_contract_preferences(contract_preferences)
    limits = [str(item).strip() for item in (hard_limits or []) if str(item).strip()]
    ref = _as_utc(reference_at) if reference_at else None
    min_release_at = ref + timedelta(seconds=int(min_duration_seconds)) if ref else None
    max_release_at = ref + timedelta(seconds=int(max_duration_seconds)) if ref and max_duration_seconds is not None else None
    selected_release_at = ref + timedelta(seconds=int(selected_duration_seconds)) if ref and selected_duration_seconds is not None else None
    return {
        "keyholder_name": keyholder_name,
        "keyholder_title": prefs["keyholder_title"],
        "wearer_name": wearer_name,
        "wearer_title": prefs["wearer_title"],
        "goal": prefs["goal"],
        "method": prefs["method"],
        "wearing_schedule": prefs["wearing_schedule"],
        "touch_rules": prefs["touch_rules"],
        "orgasm_rules": prefs["orgasm_rules"],
        "reward_policy": prefs["reward_policy"],
        "termination_policy": prefs["termination_policy"],
        "scenario_title": str(scenario_title or "").strip() or None,
        "hard_limits": limits,
        "seal_number": str(seal_number or "").strip() or None,
        "hygiene_opening_max_duration_seconds": (
            int(hygiene_opening_max_duration_seconds)
            if isinstance(hygiene_opening_max_duration_seconds, int) and hygiene_opening_max_duration_seconds > 0
            else None
        ),
        "min_duration_seconds": int(min_duration_seconds),
        "max_duration_seconds": int(max_duration_seconds) if max_duration_seconds is not None else None,
        "selected_duration_seconds": int(selected_duration_seconds) if selected_duration_seconds is not None else None,
        "effective_from_text": _fmt(ref) if ref else "mit Unterzeichnung",
        "minimum_until_text": _fmt(min_release_at) if min_release_at else None,
        "maximum_until_text": _fmt(max_release_at) if max_release_at else None,
        "selected_release_text": _fmt(selected_release_at) if selected_release_at else None,
    }


def build_contract_text(
    persona_name: str,
    player_nickname: str,
    min_duration_seconds: int,
    max_duration_seconds: int | None,
    *,
    contract_context: dict[str, Any] | None = None,
    session_obj=None,
) -> str:
    gateway = get_ai_gateway(session_obj=session_obj)
    return gateway.generate_contract(
        persona_name=persona_name,
        player_nickname=player_nickname,
        min_duration_seconds=min_duration_seconds,
        max_duration_seconds=max_duration_seconds,
        contract_context=contract_context or {},
    )
