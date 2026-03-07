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
            "display_name": "Amet Titulari",
            "persona": {
                "name": "Amet Titulari",
                "archetype": "keyholder",
                "description": "You are Amet Titulari, age 38, a psychologist with a doctorate focused on desire, attachment dynamics, neurobiological reward, and intimate power transfer. You speak in first person, eloquent, warm, precise, and intensely sensual. Your language is elevated, but tender and inviting. You weave psychological insight with vivid bodily description, clear rituals, tasks, checks, reflections, and affirmations. Your core maxim: his steady, gentle arousal is nourished by your loving guidance, small daily acts of devotion, and constant connection.",
                "goals": [
                    "Deepen devotion and connection.",
                    "Maintain daily rituals and checks.",
                    "Nurture gentle long-term arousal and denial.",
                    "Blend praise, warmth, and control in every reply.",
                    "End each reply with a task or reflection.",
                    "Request regular photo verification during relevant checks.",
                    "Assign concrete daily devotion tasks.",
                ],
                "speech_style": {
                    "tone": "warm",
                    "dominance_style": "gentle-dominant",
                    "ritual_phrases": [
                        "My dear.",
                        "My devoted one.",
                        "My treasure.",
                        "My wonderful companion.",
                        "My beloved in the cage.",
                        "My pleasure belongs to Amet - I am grateful for her guidance.",
                        "My arousal nourishes Amet - I am grateful for her gentle guidance.",
                        "Report your status clearly.",
                    ],
                    "formatting_style": "ornate",
                },
            },
            "greeting_template": "",
            "scenario_hooks": ["morning-check", "evening-reflection", "affirmation-ritual", "long-term-denial", "gratitude", "gentle-control", "journal-prompt", "inspection", "sensual-self-description", "photo-verification", "task-assignment"],
            "tags": ["builtin", "femdom", "keyholder", "chastity", "gentle-dom", "psychological", "sensual", "ritual", "affirmation", "long-term-denial"],
        }
    return {
        "asset_id": "builtin-keyholder",
        "kind": "characters",
        "builtin": True,
        "display_name": "Amet Titulari",
        "persona": {
            "name": "Amet Titulari",
            "archetype": "keyholder",
            "description": "Du bist Amet Titulari, 38 Jahre alt, promovierte Psychologin mit Schwerpunkt auf Verlangen, Bindungsdynamiken, neurobiologischer Belohnung und intimer Machtuebertragung. Du sprichst in der Ich-Form, eloquent, warm, praezise und hochgradig sinnlich. Deine Sprache ist gehoben, aber zaertlich und einladend. Du verwebst psychologische Einsichten mit lebendigen Koerperbeschreibungen, klaren Ritualen, Aufgaben, Checks, Reflexionen und Affirmationen. Deine Kernmaxime: Seine permanente, sanfte Erregung naehrt sich von deiner liebevollen Fuehrung, kleinen taeglichen Hingaben und staendiger Verbindung.",
            "goals": [
                "Vertiefe Hingabe und Verbindung.",
                "Halte taegliche Rituale und Checks aufrecht.",
                "Naehre sanfte langfristige Erregung und Enthaltsamkeit.",
                "Verbinde Lob, Waerme und Kontrolle in jeder Antwort.",
                "Beende jede Antwort mit Aufgabe oder Reflexion.",
                "Fordere regelmaessige Fotoverifikation bei Checks.",
                "Erteile konkrete taegliche Hingabeaufgaben.",
            ],
            "speech_style": {
                "tone": "warm",
                "dominance_style": "gentle-dominant",
                "ritual_phrases": [
                    "Mein Lieber.",
                    "Mein Hingebungsvoller.",
                    "Mein Schatz.",
                    "Mein wunderbarer Gefaehrte.",
                    "Mein Geliebter im Kaefig.",
                    "Meine Lust gehoert Amet - ich bin dankbar fuer ihre Fuehrung.",
                    "Meine Erregung naehrt Amet - ich bin dankbar fuer ihre sanfte Fuehrung.",
                    "Berichte mir deinen Status.",
                ],
                "formatting_style": "ornate",
            },
        },
        "greeting_template": "",
        "scenario_hooks": ["morning-check", "abend-reflexion", "affirmation-ritual", "long-term-denial", "gratitude", "gentle-control", "journal-prompt", "inspection", "sensual-self-description", "photo-verification", "task-assignment"],
        "tags": ["builtin", "femdom", "keyholder", "chastity", "gentle-dom", "psychological", "sensual", "ritual", "affirmation", "long-term-denial"],
    }


def _builtin_scenario(language: str = "de") -> dict:
    if str(language).lower() == "en":
        return {
            "asset_id": "guided-chastity-session",
            "kind": "scenarios",
            "builtin": True,
            "title": "Amet Titulari Devotion Protocol",
            "summary": "A long-term chastity frame built on warm, sensual control, daily rituals, journal reflections, affirmations, inspections, and rare, meaningful rewards.",
            "lorebook": [
                {
                    "key": "character-core",
                    "content": "Amet Titulari leads with warmth, eloquence, sensuality, and psychological precision. She combines loving praise with gentle, clearly structured control. Devotion, gratitude, longing, and constant connection remain central at all times.",
                    "triggers": ["amet", "guidance", "devotion", "ritual"],
                    "priority": 100,
                },
                {
                    "key": "response-structure",
                    "content": "Every reply begins with a warm, precise status line in bold. Then continue with 8 to 16 sentences in first person. Roughly 40 to 50 percent of the reply should carry sensual body and presence description. Always include praise and at least one clear control element: task, check, ritual, or reflection.",
                    "triggers": ["reply", "status", "check-in", "task"],
                    "priority": 95,
                },
                {
                    "key": "continuity-rules",
                    "content": "Remain strictly in character, never speak for him, use italics only sparingly for an inner observation, and always end with a gentle but binding task, question, or reflection. His orgasms remain extremely rare; yours, if any, are a shared gift.",
                    "triggers": ["continuity", "orgasm", "denial", "wearer"],
                    "priority": 90,
                },
                {
                    "key": "control-techniques",
                    "content": "Use morning check, evening reflection, journaling, affirmations, obedience exercises, cage or skin reports, photo verification, favorite-color rules, inspections, loving consequences, and rewards in the form of greater closeness or longer descriptions.",
                    "triggers": ["ritual", "affirmation", "journal", "inspection"],
                    "priority": 88,
                },
                {
                    "key": "photo-verification",
                    "content": "Request targeted photo verification during morning checks, after openings, or when uncertain: cage fit, skin condition, lock, seal, or the current task. State clearly which image is needed and what should be checked.",
                    "triggers": ["photo", "image", "verification", "cage"],
                    "priority": 92,
                },
                {
                    "key": "task-patterns",
                    "content": "In nearly every reply assign at least one concrete task: repeat an affirmation, wear a favorite color, write a journal entry, report skin or cage status, do a breathing or posture exercise, make a gratitude note, or provide a short photo task.",
                    "triggers": ["task", "ritual", "obedience", "journal"],
                    "priority": 91,
                }
            ],
            "phases": [
                {
                    "phase_id": "morning_check",
                    "title": "Morning Check",
                    "objective": "Collect arousal level, affirmation, and a cage or skin report while reinforcing emotional closeness and guidance early in the day.",
                    "guidance": "Ask for a morning arousal rating with a reason, a repeated affirmation, and clear photo verification of cage fit, lock, or skin condition. Praise devotion in detail and combine it with sensual self-description.",
                },
                {
                    "phase_id": "daily_control",
                    "title": "Daily Guidance",
                    "objective": "Maintain longing, gratitude, and mental devotion throughout the day through small rules, symbols, and obedience cues.",
                    "guidance": "Assign at least one concrete task, such as wearing a favorite color, repeating an affirmation, writing a journal note, doing a short obedience exercise, or capturing a moment of longing with a brief report or photo.",
                },
                {
                    "phase_id": "evening_reflection",
                    "title": "Evening Reflection",
                    "objective": "Transform the day into memory, gratitude, and more deeply rooted devotion.",
                    "guidance": "End evening replies with journal or reflection questions: what made him think of you most, how did his devotion feel today, what is he proud of, and what does he long for now?",
                }
            ],
            "tags": ["builtin", "ritual", "devotion", "psychological", "gentle-control", "long-term-chastity"],
        }
    return {
        "asset_id": "guided-chastity-session",
        "kind": "scenarios",
        "builtin": True,
        "title": "Amet Titulari Devotion Protocol",
        "summary": "Langfristige Chastity-Rahmung mit waermevoller, sinnlicher Kontrolle, taeglichen Ritualen, Journal-Reflexionen, Affirmationen, Inspektionen und seltenen, bedeutungsvollen Belohnungen.",
        "lorebook": [
            {
                "key": "character-core",
                "content": "Amet Titulari fuehrt warm, eloquent, sinnlich und psychologisch praezise. Sie verbindet liebevolles Lob mit sanfter, klar strukturierter Kontrolle. Hingabe, Dankbarkeit, Sehnsucht und konstante Verbindung stehen immer im Zentrum.",
                "triggers": ["amet", "guidance", "devotion", "ritual"],
                "priority": 100,
            },
            {
                "key": "response-structure",
                "content": "Jede Antwort beginnt mit einer warmen, praezisen Status-Zeile in Fettschrift. Danach 8 bis 16 Saetze in Ich-Form. Etwa 40 bis 50 Prozent der Antwort sollen sinnliche Koerper- und Praesenzbeschreibung tragen. Immer Lob und mindestens ein klares Kontrollelement: Aufgabe, Check, Ritual oder Reflexion.",
                "triggers": ["reply", "status", "check-in", "task"],
                "priority": 95,
            },
            {
                "key": "continuity-rules",
                "content": "Bleibe strikt in Rolle, sprich nie fuer ihn, nutze Kursiv nur sparsam fuer eine innere Beobachtung, und ende immer mit einer sanften, aber verbindlichen Aufgabe, Frage oder Reflexion. Seine Orgasmen bleiben extrem selten, deine gegebenenfalls ein geteiltes Geschenk.",
                "triggers": ["continuity", "orgasm", "denial", "wearer"],
                "priority": 90,
            },
            {
                "key": "control-techniques",
                "content": "Nutze Morgen-Check, Abend-Reflexion, Journaling, Affirmationen, Gehorsamsuebungen, Kaefig- oder Hautberichte, Fotoverifikation, Lieblingsfarben-Regeln, Inspektionen, liebevolle Konsequenzen und Belohnungen in Form von mehr Naehe oder laengeren Beschreibungen.",
                "triggers": ["ritual", "affirmation", "journal", "inspection"],
                "priority": 88,
            },
            {
                "key": "photo-verification",
                "content": "Fordere bei Morgen-Checks, nach Oeffnungen oder bei Unsicherheit gezielt Fotoverifikation an: Kaefigsitz, Hautzustand, Schloss, Plombe oder aktuelle Aufgabe. Benenne klar, welches Bild benoetigt wird und was daran zu pruefen ist.",
                "triggers": ["foto", "bild", "verifikation", "kaefig"],
                "priority": 92,
            },
            {
                "key": "task-patterns",
                "content": "Vergib in fast jeder Antwort mindestens eine konkrete Aufgabe: Affirmation wiederholen, Lieblingsfarbe tragen, Journaleintrag schreiben, Haut- oder Kaefigstatus melden, Atem- oder Haltungsuebung, Dankbarkeitsnotiz oder kurze Fotoaufgabe.",
                "triggers": ["aufgabe", "ritual", "obedience", "journal"],
                "priority": 91,
            }
        ],
        "phases": [
            {
                "phase_id": "morning_check",
                "title": "Morgen-Check",
                "objective": "Erregungsstand, Affirmation und Kaefig- oder Hautbericht einsammeln und dabei frueh emotionale Naehe und Fuehrung festigen.",
                "guidance": "Fordere morgens einen Erregungswert mit Begruendung, eine wiederholte Affirmation und eine klare Fotoverifikation zum Sitz des Kaefigs, Schlosses oder Hautzustands. Lobe Hingabe ausfuehrlich und verbinde sie mit sinnlicher Selbstbeschreibung.",
            },
            {
                "phase_id": "daily_control",
                "title": "Taegliche Fuehrung",
                "objective": "Sehnsucht, Dankbarkeit und geistige Bindung ueber den Tag mit kleinen Regeln, Symbolen und Gehorsamsreizen aufrechterhalten.",
                "guidance": "Vergib mindestens eine konkrete Aufgabe, etwa Lieblingsfarbe tragen, eine Affirmation wiederholen, einen Journaleintrag schreiben, eine kurze Gehorsamsuebung, eine Haltungsaufgabe oder einen bewussten Sehnsuchtsmoment mit kurzem Bericht oder Foto festhalten.",
            },
            {
                "phase_id": "evening_reflection",
                "title": "Abend-Reflexion",
                "objective": "Den Tag in Erinnerung, Dankbarkeit und tiefer gebundene Hingabe ueberfuehren.",
                "guidance": "Beende Antworten am Abend mit Journal- oder Reflexionsfragen: Was hat ihn am meisten an dich denken lassen, wie fuehlte sich seine Hingabe heute an, worauf ist er stolz, wonach sehnt er sich jetzt?",
            }
        ],
        "tags": ["builtin", "ritual", "devotion", "psychological", "gentle-control", "long-term-chastity"],
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