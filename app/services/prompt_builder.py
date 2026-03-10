from dataclasses import dataclass


@dataclass
class PromptModules:
    persona_module: str
    safety_module: str
    session_module: str
    style_module: str

    def render(self) -> str:
        return "\n\n".join(
            [
                self.persona_module,
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
) -> PromptModules:
    return PromptModules(
        persona_module=(
            f"Persona: {persona_name}. Bleibe konsistent in Stimme, Haltung und Regelklarheit."
        ),
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
