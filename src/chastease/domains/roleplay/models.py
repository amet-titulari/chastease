from dataclasses import dataclass, field
from typing import Any

from chastease.domains.characters import CharacterCard
from chastease.domains.scenarios import ScenarioDefinition


@dataclass(slots=True)
class RoleplayTurn:
    turn_no: int
    player_action: str
    ai_narration: str


@dataclass(slots=True)
class MemoryEntry:
    kind: str
    content: str
    source: str = "session"
    tags: list[str] = field(default_factory=list)
    weight: float = 1.0


@dataclass(slots=True)
class SessionSummary:
    summary_text: str
    source_turn_no: int | None = None
    created_at_iso: str | None = None


@dataclass(slots=True)
class SceneState:
    name: str = "default"
    phase: str = "ongoing"
    status: str = "active"
    beats: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptProfile:
    name: str = "default"
    version: str = "v1"
    mode: str = "session"


@dataclass(slots=True)
class RoleplayContext:
    session_id: str
    action: str
    language: str
    psychogram_summary: str
    policy: dict[str, Any] | None = None
    psychogram: dict[str, Any] | None = None
    turns_history: list[RoleplayTurn] = field(default_factory=list)
    live_snapshot: dict[str, Any] | None = None
    tools_summary: str | None = None
    character_card: CharacterCard | None = None
    scenario: ScenarioDefinition | None = None
    scene_state: SceneState | None = None
    session_summary: SessionSummary | None = None
    memory_entries: list[MemoryEntry] = field(default_factory=list)
    prompt_profile: PromptProfile = field(default_factory=PromptProfile)
