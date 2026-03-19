from dataclasses import dataclass, field
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_VERSION = "2026-03-19.1"

_PROMPT_ENV = Environment(
    loader=FileSystemLoader(str(PROMPTS_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass
class PromptModules:
    persona_module: str
    wearer_module: str
    safety_module: str
    session_module: str
    style_module: str
    scenario_module: str = ""
    version: str = PROMPT_VERSION
    templates_used: list[str] = field(default_factory=list)

    def render(self) -> str:
        return _render_prompt_template(
            "base_system_prompt.jinja2",
            persona_module=self.persona_module,
            wearer_module=self.wearer_module,
            safety_module=self.safety_module,
            session_module=self.session_module,
            style_module=self.style_module,
            scenario_module=self.scenario_module,
        )


# Maps strictness_level (1-5) to a German style directive
_STRICTNESS_STYLE = {
    1: "Sei sehr warmherzig, großzügig mit Lob, ausführlich und fürsorglich in deinen Antworten.",
    2: "Sei warm, eloquent, sinnlich und psychologisch feinfühlig. Verbinde liebevolles Lob mit sanfter Kontrolle. Antworte ausführlich und verbindend.",
    3: "Antworte klar und verbindlich, aber mit Wärme. Mische ruhige Führung mit ehrlichem Lob.",
    4: "Antworte präzise, fordernd und strukturiert. Kurze, klare Anweisungen. Lob nur bei erkennbarer Leistung.",
    5: "Antworte knapp, diszipliniert und direkt. Keine Abschweifungen. Klare Befehle und verbindliche Statusmeldungen.",
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
    strictness_level: int = 3,
    hard_limits: list[str] | None = None,
    active_phase: dict | None = None,
    lorebook_entries: list[dict] | None = None,
) -> PromptModules:
    clamped = max(1, min(5, strictness_level))
    style_directive = _STRICTNESS_STYLE[clamped]

    persona_template = _resolve_persona_template(persona_name)
    templates_used = [
        "base_system_prompt.jinja2",
        persona_template,
        "wearer_profile.jinja2",
        "safety_override.jinja2",
        "session_context.jinja2",
        "style_directive.jinja2",
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
        ),
        scenario_module=_render_prompt_template(
            "scenario_context.jinja2",
            active_phase=active_phase or {},
            lorebook_entries=lorebook_entries or [],
        ),
        templates_used=templates_used,
    )
