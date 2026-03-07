from dataclasses import dataclass, field


@dataclass(slots=True)
class SpeechStyle:
    tone: str = "balanced"
    dominance_style: str = "measured"
    ritual_phrases: list[str] = field(default_factory=list)
    formatting_style: str = "plain"


@dataclass(slots=True)
class PersonaProfile:
    name: str
    archetype: str = "keyholder"
    description: str = ""
    goals: list[str] = field(default_factory=list)
    speech_style: SpeechStyle = field(default_factory=SpeechStyle)


@dataclass(slots=True)
class CharacterCard:
    card_id: str
    display_name: str
    persona: PersonaProfile
    greeting_template: str = ""
    scenario_hooks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
