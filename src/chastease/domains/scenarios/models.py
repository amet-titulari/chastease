from dataclasses import dataclass, field


@dataclass(slots=True)
class LoreEntry:
    key: str
    content: str
    triggers: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass(slots=True)
class ScenarioPhase:
    phase_id: str
    title: str
    objective: str = ""
    guidance: str = ""


@dataclass(slots=True)
class ScenarioDefinition:
    scenario_id: str
    title: str
    summary: str = ""
    lorebook: list[LoreEntry] = field(default_factory=list)
    phases: list[ScenarioPhase] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
