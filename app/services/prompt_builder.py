from dataclasses import dataclass


@dataclass
class PromptModules:
    persona_module: str
    wearer_module: str
    safety_module: str
    session_module: str
    style_module: str
    scenario_module: str = ""

    def render(self) -> str:
        parts = [
            self.persona_module,
            self.wearer_module,
            self.safety_module,
            self.session_module,
            self.style_module,
        ]
        if self.scenario_module:
            parts.append(self.scenario_module)
        return "\n\n".join(parts)


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
    speech_style_tone: str | None = None,
    speech_style_dominance: str | None = None,
    strictness_level: int = 3,
    hard_limits: list[str] | None = None,
    active_phase: dict | None = None,
    lorebook_entries: list[dict] | None = None,
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
        if speech_style_tone:
            persona_module += f" Ton: {speech_style_tone}."
        if speech_style_dominance:
            persona_module += f" Dominanzstil: {speech_style_dominance}."
    else:
        persona_module = f"Persona: {persona_name}. Bleibe konsistent in Stimme, Haltung und Regelklarheit."
        if speech_style_tone:
            persona_module += f" Ton: {speech_style_tone}."
        if speech_style_dominance:
            persona_module += f" Dominanzstil: {speech_style_dominance}."

    clamped = max(1, min(5, strictness_level))
    style_directive = _STRICTNESS_STYLE[clamped]

    safety_module = (
        f"Safety: mode={safety_mode or 'none'}. "
        "Bei red/safeword/emergency keine spielbezogenen Eskalationen."
    )
    if hard_limits:
        limits_str = "; ".join(hard_limits)
        safety_module += (
            f" HARD LIMITS – ABSOLUT VERBOTEN (niemals in Aufgabentiteln, Beschreibungen "
            f"oder Verifikationskriterien verwenden): {limits_str}."
        )

    return PromptModules(
        persona_module=persona_module,
        wearer_module=f"Wearer-Profil: {wearer_parts}" if wearer_parts else "Wearer-Profil: keine Angaben.",
        safety_module=safety_module,
        session_module=(
            f"Session: status={session_status}. "
            f"Scenario={scenario_title or 'default'}."
        ),
        style_module=f"Stil: Antworte immer auf Deutsch. {style_directive}",
        scenario_module=_build_scenario_module(active_phase, lorebook_entries),
    )


def _build_scenario_module(
    active_phase: dict | None,
    lorebook_entries: list[dict] | None,
) -> str:
    parts: list[str] = []

    if active_phase:
        phase_title = active_phase.get("title", "")
        objective = active_phase.get("objective", "")
        guidance = active_phase.get("guidance", "")
        line = f"Aktive Phase: {phase_title}."
        if objective:
            line += f" Ziel: {objective}"
        if guidance:
            line += f" Führung: {guidance}"
        parts.append(line)

    if lorebook_entries:
        lore_lines = []
        for entry in lorebook_entries:
            key = entry.get("key", "lore")
            content = entry.get("content", "")
            if content:
                lore_lines.append(f"[{key}]: {content}")
        if lore_lines:
            parts.append("Lorebook:\n" + "\n".join(lore_lines))

    return "\n\n".join(parts)
