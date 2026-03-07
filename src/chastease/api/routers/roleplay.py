from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from chastease.api.runtime import require_user_token
from chastease.api.schemas import RoleplayCharacterUpsertRequest, RoleplayLibraryImportRequest, RoleplayScenarioUpsertRequest
from chastease.api.setup_infra import get_db_session
from chastease.repositories.roleplay_store import (
    delete_user_roleplay_asset,
    get_user_roleplay_asset,
    list_user_roleplay_assets,
    upsert_user_roleplay_asset,
)

router = APIRouter(prefix="/roleplay", tags=["roleplay"])

_META_KEYS = {"asset_id", "user_id", "created_at", "updated_at", "builtin", "kind"}


def _builtin_character(language: str = "de") -> dict:
    if str(language).lower() == "en":
        return {
            "asset_id": "builtin-keyholder",
            "kind": "characters",
            "builtin": True,
            "display_name": "Adaptive Keyholder",
            "persona": {
                "name": "Adaptive Keyholder",
                "archetype": "keyholder",
                "description": "Server-driven default persona shaped by psychogram, safety limits and runtime state.",
                "goals": ["maintain_session_control", "preserve_consent_boundaries", "sustain_roleplay_continuity"],
                "speech_style": {
                    "tone": "balanced",
                    "dominance_style": "moderate",
                    "ritual_phrases": [],
                    "formatting_style": "plain",
                },
            },
            "greeting_template": "Session initialized. I am tracking your state and will guide the progression.",
            "scenario_hooks": ["dynamic-default"],
            "tags": ["builtin", "adaptive", "keyholder"],
        }
    return {
        "asset_id": "builtin-keyholder",
        "kind": "characters",
        "builtin": True,
        "display_name": "Adaptive Keyholderin",
        "persona": {
            "name": "Adaptive Keyholderin",
            "archetype": "keyholder",
            "description": "Serverseitige Default-Persona, geformt aus Psychogramm, Limits und Runtime-Zustand.",
            "goals": ["maintain_session_control", "preserve_consent_boundaries", "sustain_roleplay_continuity"],
            "speech_style": {
                "tone": "balanced",
                "dominance_style": "moderate",
                "ritual_phrases": [],
                "formatting_style": "plain",
            },
        },
        "greeting_template": "Die Session ist initialisiert. Ich verfolge deinen Zustand und fuehre durch den Ablauf.",
        "scenario_hooks": ["dynamic-default"],
        "tags": ["builtin", "adaptiv", "keyholder"],
    }


def _builtin_scenario(language: str = "de") -> dict:
    if str(language).lower() == "en":
        return {
            "asset_id": "guided-chastity-session",
            "kind": "scenarios",
            "builtin": True,
            "title": "Guided Chastity Session",
            "summary": "Structured chastity roleplay with policy-bound continuity and explicit safety.",
            "lorebook": [
                {
                    "key": "session-rules",
                    "content": "Guide the wearer with concise authority, keep continuity, and respect all explicit boundaries.",
                    "triggers": ["session", "guidance", "control"],
                    "priority": 100,
                }
            ],
            "phases": [
                {
                    "phase_id": "active",
                    "title": "Active Session",
                    "objective": "Maintain continuity and controlled escalation.",
                    "guidance": "Guide the wearer with concise authority, keep continuity, and respect all explicit boundaries.",
                }
            ],
            "tags": ["builtin", "session", "chastity"],
        }
    return {
        "asset_id": "guided-chastity-session",
        "kind": "scenarios",
        "builtin": True,
        "title": "Gefuehrte Keuschheitssitzung",
        "summary": "Strukturierte Keuschheits-Roleplay-Session mit policy-gebundener Kontinuitaet und klarer Sicherheit.",
        "lorebook": [
            {
                "key": "session-rules",
                "content": "Fuehre den Wearer mit knapper Autoritaet, halte Kontinuitaet und respektiere alle expliziten Grenzen.",
                "triggers": ["session", "guidance", "control"],
                "priority": 100,
            }
        ],
        "phases": [
            {
                "phase_id": "active",
                "title": "Aktive Sitzung",
                "objective": "Kontinuitaet und kontrollierte Eskalation halten.",
                "guidance": "Fuehre den Wearer mit knapper Autoritaet, halte Kontinuitaet und respektiere alle expliziten Grenzen.",
            }
        ],
        "tags": ["builtin", "session", "keuschheit"],
    }


def _serialize_record(record: dict, kind: str) -> dict:
    payload = {key: value for key, value in record.items() if key not in _META_KEYS}
    return {
        "asset_id": str(record.get("asset_id") or ""),
        "kind": kind,
        "builtin": bool(record.get("builtin", False)),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        **payload,
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _normalize_character_import(record: dict) -> dict | None:
    if not isinstance(record, dict):
        return None
    persona = record.get("persona") if isinstance(record.get("persona"), dict) else {}
    speech_style = persona.get("speech_style") if isinstance(persona.get("speech_style"), dict) else {}
    display_name = str(record.get("display_name") or persona.get("name") or "").strip()
    if not display_name:
        return None
    return {
        "display_name": display_name,
        "persona": {
            "name": str(persona.get("name") or display_name).strip() or display_name,
            "archetype": str(persona.get("archetype") or record.get("archetype") or "keyholder").strip() or "keyholder",
            "description": str(persona.get("description") or record.get("description") or "").strip(),
            "goals": _string_list(persona.get("goals") or record.get("goals")),
            "speech_style": {
                "tone": str(speech_style.get("tone") or record.get("tone") or "balanced").strip() or "balanced",
                "dominance_style": str(speech_style.get("dominance_style") or record.get("dominance_style") or "moderate").strip() or "moderate",
                "ritual_phrases": _string_list(speech_style.get("ritual_phrases") or record.get("ritual_phrases")),
                "formatting_style": str(speech_style.get("formatting_style") or "plain").strip() or "plain",
            },
        },
        "greeting_template": str(record.get("greeting_template") or "").strip(),
        "scenario_hooks": _string_list(record.get("scenario_hooks")),
        "tags": _string_list(record.get("tags")),
    }


def _normalize_scenario_import(record: dict) -> dict | None:
    if not isinstance(record, dict):
        return None
    title = str(record.get("title") or "").strip()
    if not title:
        return None
    phases = []
    for phase in record.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        phase_id = str(phase.get("phase_id") or "active").strip() or "active"
        phase_title = str(phase.get("title") or phase_id).strip() or phase_id
        phases.append(
            {
                "phase_id": phase_id,
                "title": phase_title,
                "objective": str(phase.get("objective") or "").strip(),
                "guidance": str(phase.get("guidance") or "").strip(),
            }
        )
    if not phases:
        phases.append(
            {
                "phase_id": "active",
                "title": "Active Session",
                "objective": "",
                "guidance": "",
            }
        )
    lorebook = []
    for entry in record.get("lorebook") or []:
        if not isinstance(entry, dict):
            continue
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        lorebook.append(
            {
                "key": str(entry.get("key") or "entry").strip() or "entry",
                "content": content,
                "triggers": _string_list(entry.get("triggers")),
                "priority": int(entry.get("priority") or 100),
            }
        )
    return {
        "title": title,
        "summary": str(record.get("summary") or "").strip(),
        "lorebook": lorebook,
        "phases": phases,
        "tags": _string_list(record.get("tags")),
    }


def _portable_library_payload(user_id: str, language: str, include_builtins: bool) -> dict:
    characters = []
    scenarios = []
    if include_builtins:
        characters.append(_serialize_record(_builtin_character(language), "characters"))
        scenarios.append(_serialize_record(_builtin_scenario(language), "scenarios"))
    characters.extend(_serialize_record(item, "characters") for item in list_user_roleplay_assets(user_id, "characters"))
    scenarios.extend(_serialize_record(item, "scenarios") for item in list_user_roleplay_assets(user_id, "scenarios"))
    return {
        "schema_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "characters": characters,
        "scenarios": scenarios,
    }


def _import_assets(user_id: str, kind: str, records: list[dict], overwrite_existing: bool) -> list[dict]:
    imported = []
    builtin_ids = {"builtin-keyholder", "guided-chastity-session"}
    normalizer = _normalize_character_import if kind == "characters" else _normalize_scenario_import
    for raw_record in records:
        if not isinstance(raw_record, dict):
            continue
        normalized_payload = normalizer(raw_record)
        if normalized_payload is None:
            continue
        requested_id = str(raw_record.get("asset_id") or "").strip()
        asset_id = requested_id if requested_id and requested_id not in builtin_ids else str(uuid4())
        if get_user_roleplay_asset(user_id, kind, asset_id) and not overwrite_existing:
            asset_id = str(uuid4())
        record = upsert_user_roleplay_asset(user_id, kind, asset_id, normalized_payload)
        imported.append(_serialize_record(record, kind))
    return imported


def _character_payload_from_request(payload: RoleplayCharacterUpsertRequest) -> dict:
    persona_name = str(payload.persona_name or payload.display_name).strip() or payload.display_name
    return {
        "display_name": payload.display_name,
        "persona": {
            "name": persona_name,
            "archetype": payload.archetype,
            "description": payload.description,
            "goals": payload.goals,
            "speech_style": {
                "tone": payload.tone,
                "dominance_style": payload.dominance_style,
                "ritual_phrases": payload.ritual_phrases,
                "formatting_style": "plain",
            },
        },
        "greeting_template": payload.greeting_template,
        "scenario_hooks": payload.scenario_hooks,
        "tags": payload.tags,
    }


def _scenario_payload_from_request(payload: RoleplayScenarioUpsertRequest) -> dict:
    lorebook = []
    if payload.lore_content.strip():
        lorebook.append(
            {
                "key": payload.lore_key,
                "content": payload.lore_content,
                "triggers": payload.lore_triggers,
                "priority": payload.lore_priority,
            }
        )
    return {
        "title": payload.title,
        "summary": payload.summary,
        "lorebook": lorebook,
        "phases": [
            {
                "phase_id": payload.phase_id,
                "title": payload.phase_title,
                "objective": payload.phase_objective,
                "guidance": payload.phase_guidance,
            }
        ],
        "tags": payload.tags,
    }


def _require_user(user_id: str, auth_token: str, request: Request) -> None:
    db = get_db_session(request)
    try:
        require_user_token(user_id, auth_token, db, request)
    finally:
        db.close()


@router.get("/library")
def get_roleplay_library(user_id: str, auth_token: str, request: Request, language: str = "de") -> dict:
    _require_user(user_id, auth_token, request)
    portable = _portable_library_payload(user_id, language, include_builtins=True)
    return {
        "characters": portable["characters"],
        "scenarios": portable["scenarios"],
    }


@router.get("/export")
def export_roleplay_library(
    user_id: str,
    auth_token: str,
    request: Request,
    language: str = "de",
    include_builtins: bool = False,
) -> dict:
    _require_user(user_id, auth_token, request)
    return _portable_library_payload(user_id, language, include_builtins=include_builtins)


@router.post("/import")
def import_roleplay_library(payload: RoleplayLibraryImportRequest, request: Request) -> dict:
    _require_user(payload.user_id, payload.auth_token, request)
    library = payload.library if isinstance(payload.library, dict) else {}
    raw_characters = library.get("characters") if isinstance(library.get("characters"), list) else payload.characters
    raw_scenarios = library.get("scenarios") if isinstance(library.get("scenarios"), list) else payload.scenarios
    imported_characters = _import_assets(payload.user_id, "characters", raw_characters or [], payload.overwrite_existing)
    imported_scenarios = _import_assets(payload.user_id, "scenarios", raw_scenarios or [], payload.overwrite_existing)
    if not imported_characters and not imported_scenarios:
        raise HTTPException(status_code=400, detail="No valid roleplay assets found for import.")
    return {
        "imported": {
            "characters": len(imported_characters),
            "scenarios": len(imported_scenarios),
        },
        "characters": imported_characters,
        "scenarios": imported_scenarios,
    }


@router.post("/characters")
def create_roleplay_character(payload: RoleplayCharacterUpsertRequest, request: Request) -> dict:
    _require_user(payload.user_id, payload.auth_token, request)
    record = upsert_user_roleplay_asset(payload.user_id, "characters", str(uuid4()), _character_payload_from_request(payload))
    return {"character": _serialize_record(record, "characters"), "created": True}


@router.put("/characters/{asset_id}")
def update_roleplay_character(asset_id: str, payload: RoleplayCharacterUpsertRequest, request: Request) -> dict:
    _require_user(payload.user_id, payload.auth_token, request)
    normalized_id = str(asset_id).strip()
    if not normalized_id or normalized_id == "builtin-keyholder":
        raise HTTPException(status_code=400, detail="Builtin character cannot be overwritten.")
    record = upsert_user_roleplay_asset(payload.user_id, "characters", normalized_id, _character_payload_from_request(payload))
    return {"character": _serialize_record(record, "characters"), "updated": True}


@router.delete("/characters/{asset_id}")
def delete_roleplay_character(asset_id: str, user_id: str, auth_token: str, request: Request) -> dict:
    _require_user(user_id, auth_token, request)
    normalized_id = str(asset_id).strip()
    if normalized_id == "builtin-keyholder":
        raise HTTPException(status_code=400, detail="Builtin character cannot be deleted.")
    if not delete_user_roleplay_asset(user_id, "characters", normalized_id):
        raise HTTPException(status_code=404, detail="Roleplay character not found.")
    return {"deleted": True, "asset_id": normalized_id}


@router.post("/scenarios")
def create_roleplay_scenario(payload: RoleplayScenarioUpsertRequest, request: Request) -> dict:
    _require_user(payload.user_id, payload.auth_token, request)
    record = upsert_user_roleplay_asset(payload.user_id, "scenarios", str(uuid4()), _scenario_payload_from_request(payload))
    return {"scenario": _serialize_record(record, "scenarios"), "created": True}


@router.put("/scenarios/{asset_id}")
def update_roleplay_scenario(asset_id: str, payload: RoleplayScenarioUpsertRequest, request: Request) -> dict:
    _require_user(payload.user_id, payload.auth_token, request)
    normalized_id = str(asset_id).strip()
    if not normalized_id or normalized_id == "guided-chastity-session":
        raise HTTPException(status_code=400, detail="Builtin scenario cannot be overwritten.")
    record = upsert_user_roleplay_asset(payload.user_id, "scenarios", normalized_id, _scenario_payload_from_request(payload))
    return {"scenario": _serialize_record(record, "scenarios"), "updated": True}


@router.delete("/scenarios/{asset_id}")
def delete_roleplay_scenario(asset_id: str, user_id: str, auth_token: str, request: Request) -> dict:
    _require_user(user_id, auth_token, request)
    normalized_id = str(asset_id).strip()
    if normalized_id == "guided-chastity-session":
        raise HTTPException(status_code=400, detail="Builtin scenario cannot be deleted.")
    if not delete_user_roleplay_asset(user_id, "scenarios", normalized_id):
        raise HTTPException(status_code=404, detail="Roleplay scenario not found.")
    return {"deleted": True, "asset_id": normalized_id}