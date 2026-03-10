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


# Maps strictness_level (1-5) to a German style directive
_STRICTNESS_STYLE = {
    1: "Sei sehr warmherzig, großzügig mit Lob, ausführlich und fürsorglich in deinen Antworten.",
    2: "Sei warm, eloquent, sinnlich und psychologisch feinfühlig. Verbinde liebevolles Lob mit sanfter Kontrolle. Antworte ausführlich und verbindend.",
    3: "Antworte klar und verbindlich, aber mit Wärme. Mische ruhige Führung mit ehrlichem Lob.",
    4: "Antworte präzise, fordernd und strukturiert. Kurze, klare Anweisungen. Lob nur bei erkennbarer Leistung.",
    5: "Antworte knapp, diszipliniert und direkt. Keine Abschweifungen. Klare Befehle und verbindliche Statusmeldungen.",
}


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
    communication_style: str | None = None,
    strictness_level: int = 3,
) -> PromptModules:
    nickname_part = f"Wearer: {wearer_nickname}." if wearer_nickname else "Wearer: unbekannt."
    level_part = f"Erfahrungslevel: {experience_level}." if experience_level else ""
    style_part = f"Bevorzugter Stil: {wearer_style}." if wearer_style else ""
    goal_part = f"Ziel: {wearer_goal}." if wearer_goal else ""
    boundary_part = f"Grenzen/Limits: {wearer_boundary}." if wearer_boundary else ""
    wearer_parts = " ".join(p for p in [nickname_part, level_part, style_part, goal_part, boundary_part] if p)

    # Build persona module: prefer the stored system_prompt, fall back to name
    if persona_system_prompt:
        persona_module = persona_system_prompt
        if communication_style:
            persona_module += f" Kommunikationsstil: {communication_style}."
    else:
        persona_module = f"Persona: {persona_name}. Bleibe konsistent in Stimme, Haltung und Regelklarheit."
        if communication_style:
            persona_module += f" Kommunikationsstil: {communication_style}."

    clamped = max(1, min(5, strictness_level))
    style_directive = _STRICTNESS_STYLE[clamped]

    return PromptModules(
        persona_module=persona_module,
        wearer_module=f"Wearer-Profil: {wearer_parts}" if wearer_parts else "Wearer-Profil: keine Angaben.",
        safety_module=(
            f"Safety: mode={safety_mode or 'none'}. "
            "Bei red/safeword/emergency keine spielbezogenen Eskalationen."
        ),
        session_module=(
            f"Session: status={session_status}. "
            f"Scenario={scenario_title or 'default'}."
        ),
        style_module=f"Stil: Antworte immer auf Deutsch. {style_directive}",
    )
