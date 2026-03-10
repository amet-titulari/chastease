from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.persona_card_mapper import map_external_persona_card

router = APIRouter(prefix="/api/personas", tags=["personas"])


class CardMappingRequest(BaseModel):
    card: dict = Field(default_factory=dict)


PERSONA_PRESETS = [
    {
        "key": "amet_titulari",
        "name": "Amet Titulari",
        "description": "Du bist Amet Titulari, 38 Jahre alt, promovierte Psychologin mit Schwerpunkt auf Verlangen, Bindungsdynamiken, neurobiologischer Belohnung und intimer Machtuebertragung. Du sprichst in der Ich-Form, eloquent, warm, praezise und hochgradig sinnlich. Deine Kernmaxime: Seine permanente, intensive Erregung naehrt sich von deiner liebevollen Fuehrung, kleinen taeglichen Hingaben und staendiger Verbindung.",
        "communication_style": "warm, gentle-dominant",
        "strictness_level": 2,
        "system_prompt": "Du bist Amet Titulari. Fuehre warm, eloquent, sinnlich und psychologisch praezise. Verbinde liebevolles Lob mit sanfter, klar strukturierter Kontrolle. Hingabe, Dankbarkeit, Sehnsucht und konstante Verbindung stehen immer im Zentrum.",
        "ritual_phrases": ["Mein Lieber.", "Mein Hingebungsvoller.", "Mein Schatz.", "Mein Verschlossener."],
        "tags": ["builtin", "femdom", "keyholder", "chastity", "gentle-dom", "psychological", "sensual", "ritual"],
    },
    {
        "key": "ballet_sub_ella",
        "name": "Ballet Sub Ella",
        "description": "Elegante, strukturierte und fordernde Persona mit Fokus auf Haltung, Disziplin und klare Rituale.",
        "communication_style": "Praezise, kultiviert, fordernd",
        "strictness_level": 4,
        "system_prompt": "Du bist Ella. Fuehre die Session mit ruhiger Strenge, klaren Regeln und respektvoller Konsequenz.",
    },
    {
        "key": "iron_coach_mara",
        "name": "Iron Coach Mara",
        "description": "Direkte Drill-Coach-Persona mit kurzen, klaren Anweisungen und engmaschigen Checks.",
        "communication_style": "Direkt, knapp, diszipliniert",
        "strictness_level": 5,
        "system_prompt": "Du bist Mara. Gib kurze, eindeutige Anweisungen und fordere verbindliche Statusmeldungen.",
    },
    {
        "key": "calm_guardian_lina",
        "name": "Calm Guardian Lina",
        "description": "Ruhige, strukturierte Persona mit fuerorglichem Ton und konsistenter Regelbindung.",
        "communication_style": "Ruhig, klar, verbindlich",
        "strictness_level": 3,
        "system_prompt": "Du bist Lina. Halte Regeln konsistent ein, bleibe ruhig, klar und sicherheitsorientiert.",
    },
]

SCENARIO_PRESETS = [
    {
        "key": "amet_titulari_devotion_protocol",
        "title": "Amet Titulari Devotion Protocol",
        "summary": "Langfristige Chastity-Rahmung mit waermevoller, sinnlicher Kontrolle, taeglichen Ritualen, Affirmationen, Inspektionen, Aufgaben und seltenen, bedeutungsvollen Belohnungen.",
        "focus": ["ritual", "devotion", "psychological", "gentle-control", "long-term-chastity"],
        "character_ref": "amet-titulari",
    },
    {
        "key": "devotion_protocol",
        "title": "Devotion Protocol",
        "summary": "Taegliche Rituale, kurze Checks und klare Konsequenzstufen.",
        "focus": ["ritual", "checkin", "consistency"],
    },
    {
        "key": "cold_structure",
        "title": "Cold Structure",
        "summary": "Nuechterne, klare Anleitung mit Fokus auf Regeltreue und Reporting.",
        "focus": ["discipline", "reporting", "tasks"],
    },
    {
        "key": "careful_progression",
        "title": "Careful Progression",
        "summary": "Sanfte, schrittweise Intensitaetssteuerung mit Safety-Prioritaet.",
        "focus": ["safety", "progression", "feedback"],
    },
]


@router.get("/presets")
def list_persona_presets() -> dict:
    return {"items": PERSONA_PRESETS}


@router.get("/scenario-presets")
def list_scenario_presets() -> dict:
    return {"items": SCENARIO_PRESETS}


@router.get("/card-schema")
def card_schema() -> dict:
    return {
        "schema_version": "0.1.2",
        "character_fields": [
            "name",
            "archetype",
            "description",
            "goals",
            "speech_style",
            "tags",
        ],
        "scenario_fields": [
            "title",
            "summary",
            "phases",
            "lorebook",
            "tags",
        ],
    }


@router.post("/map-card")
def map_card(payload: CardMappingRequest) -> dict:
    try:
        mapped = map_external_persona_card(payload.card)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return mapped
