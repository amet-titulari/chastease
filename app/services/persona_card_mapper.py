import re


def _slugify(value: str, fallback: str = "imported_persona") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or fallback


def _style_to_strictness(dominance_style: str) -> int:
    token = dominance_style.strip().lower()
    if token in {"strict", "hard-dominant"}:
        return 5
    if token in {"dominant", "firm"}:
        return 4
    if token in {"gentle-dominant", "balanced"}:
        return 3
    if token in {"supportive", "soft"}:
        return 2
    return 3


def _map_role_style(tone: str, dominance_style: str) -> str:
    t = tone.strip().lower()
    d = dominance_style.strip().lower()
    if d in {"strict", "hard-dominant", "dominant", "firm"}:
        return "strict"
    if t in {"warm", "soft", "empathetic", "caring"}:
        return "supportive"
    return "structured"


def map_external_persona_card(payload: dict) -> dict:
    warnings: list[str] = []

    characters = payload.get("characters", [])
    if not isinstance(characters, list) or not characters:
        raise ValueError("No characters found in payload")

    scenarios = payload.get("scenarios", [])
    if not isinstance(scenarios, list):
        scenarios = []

    character = characters[0]
    persona = character.get("persona", {}) if isinstance(character, dict) else {}

    name = str(persona.get("name") or character.get("display_name") or "Imported Persona").strip()
    description = str(persona.get("description") or "").strip()
    goals = persona.get("goals", [])
    if not isinstance(goals, list):
        goals = []
    goals = [str(item).strip() for item in goals if str(item).strip()]

    speech_style = persona.get("speech_style", {}) if isinstance(persona, dict) else {}
    tone = str(speech_style.get("tone") or "neutral")
    dominance_style = str(speech_style.get("dominance_style") or "balanced")
    ritual_phrases = speech_style.get("ritual_phrases", [])
    if not isinstance(ritual_phrases, list):
        ritual_phrases = []
    ritual_phrases = [str(item).strip() for item in ritual_phrases if str(item).strip()]

    tags = character.get("tags", []) if isinstance(character, dict) else []
    if not isinstance(tags, list):
        tags = []
    tags = [str(item).strip() for item in tags if str(item).strip()]

    scenario = scenarios[0] if scenarios and isinstance(scenarios[0], dict) else {}
    scenario_title = str(scenario.get("title") or "Imported Scenario").strip()
    scenario_summary = str(scenario.get("summary") or "").strip()

    scenario_tags = scenario.get("tags", []) if isinstance(scenario, dict) else []
    if not isinstance(scenario_tags, list):
        scenario_tags = []
    scenario_tags = [str(item).strip() for item in scenario_tags if str(item).strip()]

    if not description:
        warnings.append("Persona description is empty")
    if not goals:
        warnings.append("Persona goals are empty")
    if not scenario_summary:
        warnings.append("Scenario summary is empty")

    strictness_level = _style_to_strictness(dominance_style)
    role_style = _map_role_style(tone=tone, dominance_style=dominance_style)

    communication_parts = [tone.strip(), dominance_style.strip()]
    communication_style = ", ".join(part for part in communication_parts if part)

    lorebook_items = scenario.get("lorebook", []) if isinstance(scenario, dict) else []
    if not isinstance(lorebook_items, list):
        lorebook_items = []

    phases = scenario.get("phases", []) if isinstance(scenario, dict) else []
    if not isinstance(phases, list):
        phases = []

    return {
        "schema_version": "0.1.2",
        "persona_preset": {
            "key": _slugify(name),
            "name": name,
            "description": description,
            "communication_style": communication_style,
            "strictness_level": strictness_level,
            "system_prompt": (
                f"Du bist {name}. Ton={tone}. Dominance={dominance_style}. "
                "Bleibe klar, konsistent und safety-konform."
            ),
            "goals": goals,
            "ritual_phrases": ritual_phrases,
            "tags": tags,
        },
        "scenario_preset": {
            "key": _slugify(scenario_title, fallback="imported_scenario"),
            "title": scenario_title,
            "summary": scenario_summary,
            "focus": scenario_tags[:6],
            "lorebook": lorebook_items,
            "phases": phases,
        },
        "setup_defaults": {
            "role_style": role_style,
            "primary_goal_suggestions": goals[:5],
            "boundary_suggestions": [
                "Keine Aufgaben waehrend Arbeit oder Meetings",
                "Keine Eskalation ohne vorheriges Einverstaendnis",
            ],
        },
        "warnings": warnings,
    }
