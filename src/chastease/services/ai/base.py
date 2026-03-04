from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TurnHistoryEntry:
    turn_no: int
    player_action: str
    ai_narration: str


@dataclass
class StoryTurnContext:
    session_id: str
    action: str
    language: str
    psychogram_summary: str
    turns_history: list[TurnHistoryEntry] = field(default_factory=list)
    live_snapshot: dict[str, Any] | None = None
    tools_summary: str | None = None
    policy: dict[str, Any] | None = None


class AIService(Protocol):
    def generate_narration(self, context: StoryTurnContext) -> str:
        ...
