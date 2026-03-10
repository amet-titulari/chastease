from fastapi import APIRouter

router = APIRouter(prefix="/api/personas", tags=["personas"])


PERSONA_PRESETS = [
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
