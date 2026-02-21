from .base import StoryTurnContext


class OpenAIAdapter:
    """First OpenAI adapter with deterministic fallback for local/dev usage."""

    def __init__(self, model: str, api_key: str = ""):
        self.model = model
        self.api_key = api_key

    def generate_narration(self, context: StoryTurnContext) -> str:
        if not self.api_key:
            if context.language == "en":
                return (
                    f"Keyholder notes your action '{context.action}'. "
                    f"Based on your profile ({context.psychogram_summary}), "
                    "the session continues with measured control."
                )
            return (
                f"Keyholder registriert deine Aktion '{context.action}'. "
                f"Basierend auf deinem Profil ({context.psychogram_summary}) "
                "wird die Session kontrolliert fortgesetzt."
            )

        # Placeholder for real API call path.
        if context.language == "en":
            return (
                f"[{self.model}] Action '{context.action}' accepted. "
                "Session remains in controlled progression."
            )
        return (
            f"[{self.model}] Aktion '{context.action}' akzeptiert. "
            "Die Session bleibt in kontrollierter Entwicklung."
        )
