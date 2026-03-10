from dataclasses import dataclass


@dataclass
class PromptModules:
    persona_module: str
    wearer_module: str
    safety_module: str
    session_module: str
    style_module: str

    def render(self) -> str:
        return "\n\n".join(
            [
                self.persona_module,
                self.wearer_module,
                self.safety_module,
                self.session_module,
                self.style_module,
            ]
        )


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
) -> PromptModules:
    nickname_part = f"Wearer: {wearer_nickname}." if wearer_nickname else "Wearer: unbekannt."
    level_part = f"Erfahrungslevel: {experience_level}." if experience_level else ""
    style_part = f"Bevorzugter Stil: {wearer_style}." if wearer_style else ""
    goal_part = f"Ziel: {wearer_goal}." if wearer_goal else ""
    boundary_part = f"Grenzen/Limits: {wearer_boundary}." if wearer_boundary else ""
    wearer_parts = " ".join(p for p in [nickname_part, level_part, style_part, goal_part, boundary_part] if p)

    return PromptModules(
        persona_module=(
            f"Persona: {persona_name}. Bleibe konsistent in Stimme, Haltung und Regelklarheit."
        ),
        wearer_module=f"Wearer-Profil: {wearer_parts}" if wearer_parts else "Wearer-Profil: keine Angaben.",
        safety_module=(
            f"Safety: mode={safety_mode or 'none'}. "
            "Bei red/safeword/emergency keine spielbezogenen Eskalationen."
        ),
        session_module=(
            f"Session: status={session_status}. "
            f"Scenario={scenario_title or 'default'}."
        ),
        style_module=(
            "Stil: antworte knapp, konkret, ruhig und handlungsorientiert auf Deutsch."
        ),
    )
