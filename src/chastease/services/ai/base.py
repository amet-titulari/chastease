from dataclasses import dataclass
from typing import Protocol


@dataclass
class StoryTurnContext:
    session_id: str
    action: str
    language: str
    psychogram_summary: str


class AIService(Protocol):
    def generate_narration(self, context: StoryTurnContext) -> str:
        ...
