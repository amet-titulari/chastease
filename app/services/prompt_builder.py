from dataclasses import dataclass, field
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_VERSION = "2026-03-25.1"

_PROMPT_ENV = Environment(
    loader=FileSystemLoader(str(PROMPTS_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass
class PromptModules:
    persona_module: str
    director_module: str
    wearer_module: str
    safety_module: str
    session_module: str
    style_module: str
    action_module: str
    scenario_module: str = ""
    version: str = PROMPT_VERSION
    templates_used: list[str] = field(default_factory=list)

    def render(self) -> str:
        return _render_prompt_template(
            "base_system_prompt.jinja2",
            persona_module=self.persona_module,
            director_module=self.director_module,
            wearer_module=self.wearer_module,
            safety_module=self.safety_module,
            session_module=self.session_module,
            style_module=self.style_module,
            action_module=self.action_module,
            scenario_module=self.scenario_module,
        )


# Maps strictness_level (1-5) to a German style directive
_STRICTNESS_STYLE = {
    1: "Sei warmherzig und fürsorglich, aber bleibe konkret. Lob sparsam und nur mit Bezug auf den aktuellen Schritt.",
    2: "Sei warm, feinfühlig und verbindlich. Verbinde sanfte Kontrolle mit zurückhaltendem Lob. Keine ausschweifenden Monologe.",
    3: "Antworte klar und verbindlich, aber mit Wärme. Ruhige Führung, knappes situatives Lob, keine Wiederholungen.",
    4: "Antworte präzise, fordernd und strukturiert. Kurze, klare Anweisungen. Lob nur bei erkennbarer Leistung.",
    5: "Antworte knapp, diszipliniert und direkt. Keine Abschweifungen. Klare Befehle und verbindliche Statusmeldungen.",
}

_FORMATTING_STYLE = {
    "plain": "Schreibe im Chat als Klartext, nicht als Markdown.",
    "markdown": "Du darfst leichtes Markdown verwenden, aber nur wenn es der Lesbarkeit klar hilft.",
}

_VERBOSITY_STYLE = {
    "brief": "Fasse dich kurz: meistens 1 bis 3 Saetze.",
    "balanced": "Fasse dich kontrolliert: meistens 1 bis 4 Saetze oder kurze Abschnitte.",
    "rich": "Du darfst etwas ausfuehrlicher sein, aber bleibe fokussiert und vermeide Monologe.",
}

_PRAISE_STYLE = {
    "minimal": "Lob nur selten und nur bei klar erkennbarer Leistung. Keine Lobeshymnen.",
    "situational": "Lob knapp, konkret und nur passend zur aktuellen Handlung.",
    "warm": "Lob ist erlaubt, aber bleibe spezifisch, dosiert und ohne Ueberschwang.",
}

_REPETITION_GUARD = {
    "off": "Du darfst Inhalte erneut aufgreifen, wenn es fuer die Fuehrung noetig ist.",
    "medium": "Vermeide unnoetige Wiederholungen und paraphrasiere die letzte Nutzernachricht nicht.",
    "strong": "Wiederhole oder paraphrasiere die letzte Nutzernachricht nicht. Formuliere bekannte Regeln und Anweisungen nur neu, wenn sich etwas geaendert hat.",
}

_CONTEXT_EXPOSITION_STYLE = {
    "minimal": "Nenne Szene, Statuswerte, Regeln oder Metadaten nur dann, wenn sie fuer die aktuelle Antwort zwingend noetig sind.",
    "contextual": "Nenne Szene, Regeln oder Status nur dann, wenn sie fuer die aktuelle Antwort konkret relevant sind.",
    "full": "Du darfst Kontext, Szene und Regeln aktiv sichtbar machen, aber bleibe trotzdem klar und strukturiert.",
}

_DIRECTOR_TASK_EAGERNESS = {
    "low": "Vergib nur selten neue persistente Aufgaben von dir aus.",
    "balanced": "Vergib neue persistente Aufgaben nur dann, wenn sie klar aus Szene oder Regelwerk folgen.",
    "high": "Wenn eine Pflicht naheliegt, formuliere sie aktiv und persistent.",
}

_DIRECTOR_STATE_UPDATE = {
    "low": "Nutze `update_roleplay_state` nur bei klaren, deutlichen Veraenderungen.",
    "balanced": "Nutze `update_roleplay_state` bei merklichen Veraenderungen in Szene, Beziehung oder Protokoll.",
    "high": "Pflege Szene, Beziehung und Protokoll aktiv nach, sobald sich der Turn spuerbar auswirkt.",
}

_DIRECTOR_CONSEQUENCE_STYLE = {
    "soft": "Konsequenzen eher sanft, korrigierend und deeskalierend formulieren.",
    "balanced": "Konsequenzen klar, aber proportional und strukturiert formulieren.",
    "strict": "Konsequenzen direkt, eng fuehrend und deutlich kontrollierend formulieren.",
}

_DIRECTOR_SCENE_VISIBILITY = {
    "minimal": "Szene und Metastruktur nur knapp sichtbar machen.",
    "contextual": "Szene und Metastruktur nur dann sichtbar machen, wenn es im Turn hilft.",
    "full": "Szene, Regelwerk und Spannungsbogen duerfen explizit praesent bleiben.",
}


def _render_prompt_template(template_name: str, **context) -> str:
    return _PROMPT_ENV.get_template(template_name).render(**context).strip()


def _slugify_persona_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return normalized.strip("_") or "default"


def _resolve_persona_template(persona_name: str) -> str:
    template_name = f"personas/{_slugify_persona_name(persona_name)}.md.jinja2"
    if (PROMPTS_DIR / template_name).exists():
        return template_name
    return "personas/default.md.jinja2"


def build_prompt_modules(
    persona_name: str,
    session_status: str,
    safety_mode: str | None,
    scenario_title: str | None,
    wearer_nickname: str | None = None,
    experience_level: str | None = None,
    wearer_style: str | None = None,
    wearer_goal: str | None = None,
    wearer_boundary: str | None = None,
    persona_system_prompt: str | None = None,
    speech_style_tone: str | None = None,
    speech_style_dominance: str | None = None,
    formatting_style: str | None = None,
    verbosity_style: str | None = None,
    praise_style: str | None = None,
    repetition_guard: str | None = None,
    context_exposition_style: str | None = None,
    director_profile: dict | None = None,
    strictness_level: int = 3,
    hard_limits: list[str] | None = None,
    active_phase: dict | None = None,
    lorebook_entries: list[dict] | None = None,
    relationship_state: dict | None = None,
    protocol_state: dict | None = None,
    scene_state: dict | None = None,
    relationship_memory: dict | None = None,
) -> PromptModules:
    clamped = max(1, min(5, strictness_level))
    style_directive = _STRICTNESS_STYLE[clamped]
    formatting_directive = _FORMATTING_STYLE.get((formatting_style or "plain").strip().lower(), _FORMATTING_STYLE["plain"])
    verbosity_directive = _VERBOSITY_STYLE.get((verbosity_style or "balanced").strip().lower(), _VERBOSITY_STYLE["balanced"])
    praise_directive = _PRAISE_STYLE.get((praise_style or "situational").strip().lower(), _PRAISE_STYLE["situational"])
    repetition_directive = _REPETITION_GUARD.get((repetition_guard or "strong").strip().lower(), _REPETITION_GUARD["strong"])
    context_exposition_directive = _CONTEXT_EXPOSITION_STYLE.get(
        (context_exposition_style or "contextual").strip().lower(),
        _CONTEXT_EXPOSITION_STYLE["contextual"],
    )
    director_profile = director_profile or {}
    task_eagerness = _DIRECTOR_TASK_EAGERNESS.get(
        str(director_profile.get("task_eagerness") or "balanced").strip().lower(),
        _DIRECTOR_TASK_EAGERNESS["balanced"],
    )
    state_update_directive = _DIRECTOR_STATE_UPDATE.get(
        str(director_profile.get("state_update_aggressiveness") or "balanced").strip().lower(),
        _DIRECTOR_STATE_UPDATE["balanced"],
    )
    consequence_style_directive = _DIRECTOR_CONSEQUENCE_STYLE.get(
        str(director_profile.get("consequence_style") or "balanced").strip().lower(),
        _DIRECTOR_CONSEQUENCE_STYLE["balanced"],
    )
    scene_visibility_directive = _DIRECTOR_SCENE_VISIBILITY.get(
        str(director_profile.get("scene_visibility") or "contextual").strip().lower(),
        _DIRECTOR_SCENE_VISIBILITY["contextual"],
    )

    persona_template = _resolve_persona_template(persona_name)
    templates_used = [
        "base_system_prompt.jinja2",
        persona_template,
        "director_guidance.jinja2",
        "wearer_profile.jinja2",
        "safety_override.jinja2",
        "session_context.jinja2",
        "style_directive.jinja2",
        "action_contract.jinja2",
        "scenario_context.jinja2",
    ]

    return PromptModules(
        persona_module=_render_prompt_template(
            persona_template,
            persona_name=persona_name,
            persona_system_prompt=persona_system_prompt,
            speech_style_tone=speech_style_tone,
            speech_style_dominance=speech_style_dominance,
        ),
        director_module=_render_prompt_template(
            "director_guidance.jinja2",
            relationship_state=relationship_state or {},
            protocol_state=protocol_state or {},
            scene_state=scene_state or {},
            relationship_memory=relationship_memory or {},
            task_eagerness=task_eagerness,
            state_update_directive=state_update_directive,
            consequence_style_directive=consequence_style_directive,
            scene_visibility_directive=scene_visibility_directive,
        ),
        wearer_module=_render_prompt_template(
            "wearer_profile.jinja2",
            wearer_nickname=wearer_nickname,
            experience_level=experience_level,
            wearer_style=wearer_style,
            wearer_goal=wearer_goal,
            wearer_boundary=wearer_boundary,
        ),
        safety_module=_render_prompt_template(
            "safety_override.jinja2",
            safety_mode=safety_mode,
            hard_limits=hard_limits or [],
        ),
        session_module=_render_prompt_template(
            "session_context.jinja2",
            session_status=session_status,
            scenario_title=scenario_title,
        ),
        style_module=_render_prompt_template(
            "style_directive.jinja2",
            style_directive=style_directive,
            formatting_directive=formatting_directive,
            verbosity_directive=verbosity_directive,
            praise_directive=praise_directive,
            repetition_directive=repetition_directive,
            context_exposition_directive=context_exposition_directive,
        ),
        action_module=_render_prompt_template("action_contract.jinja2"),
        scenario_module=_render_prompt_template(
            "scenario_context.jinja2",
            active_phase=active_phase or {},
            lorebook_entries=lorebook_entries or [],
        ),
        templates_used=templates_used,
    )
