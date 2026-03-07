from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from chastease.api.runtime import require_user_token
from chastease.api.schemas import RoleplayCharacterUpsertRequest, RoleplayScenarioUpsertRequest
from chastease.api.setup_infra import get_db_session
from chastease.repositories.roleplay_store import (
    delete_user_roleplay_asset,
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
    characters = [_serialize_record(_builtin_character(language), "characters")]
    characters.extend(_serialize_record(item, "characters") for item in list_user_roleplay_assets(user_id, "characters"))
    scenarios = [_serialize_record(_builtin_scenario(language), "scenarios")]
    scenarios.extend(_serialize_record(item, "scenarios") for item in list_user_roleplay_assets(user_id, "scenarios"))
    return {
        "characters": characters,
        "scenarios": scenarios,
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