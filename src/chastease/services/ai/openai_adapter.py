import httpx

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

    def generate_narration_with_profile(
        self,
        context: StoryTurnContext,
        *,
        api_url: str,
        api_key: str,
        chat_model: str,
        behavior_prompt: str = "",
    ) -> str:
        if not api_url or not api_key or not chat_model:
            return self.generate_narration(context)

        system_prompt = (
            "You are a safe roleplay keyholder assistant. "
            "Respect explicit hard limits and safety constraints."
        )
        if behavior_prompt.strip():
            system_prompt = f"{system_prompt}\n\nBehavior profile:\n{behavior_prompt.strip()}"

        user_prompt = (
            f"Session: {context.session_id}\n"
            f"Psychogram summary: {context.psychogram_summary}\n"
            f"Wearer action: {context.action}\n"
            f"Language: {context.language}\n"
            "Respond as the keyholder with concise narrative and next guidance."
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }

        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return self.generate_narration(context)
