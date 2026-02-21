import httpx

from .base import StoryTurnContext


class OpenAIAdapter:
    """First OpenAI adapter with deterministic fallback for local/dev usage."""

    def __init__(self, model: str, api_key: str = ""):
        self.model = model
        self.api_key = api_key

    @staticmethod
    def _parse_psychogram_summary(summary: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for part in summary.split(";"):
            piece = part.strip()
            if not piece or "=" not in piece:
                continue
            key, value = piece.split("=", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    @staticmethod
    def _is_analysis_request(action: str, language: str) -> bool:
        text = action.lower()
        if language == "en":
            return any(token in text for token in ["analy", "profile", "psychogram"])
        return any(token in text for token in ["analys", "psychogram", "profil"])

    def _analysis_fallback(self, context: StoryTurnContext) -> str:
        profile = self._parse_psychogram_summary(context.psychogram_summary or "")
        escalation = profile.get("escalation_mode", "moderate")
        experience = profile.get("experience", "5/intermediate")
        safety = profile.get("safety", "mode=safeword")
        intensity = profile.get("intensity", "2")
        instruction_style = profile.get("instruction_style", "mixed")

        if context.language == "en":
            return (
                "Psychogram analysis: I will lead with clear structure, controlled pacing and consistent boundaries. "
                f"Current steering: escalation={escalation}, intensity={intensity}, instruction style={instruction_style}. "
                f"Experience calibration={experience}; safety baseline={safety}. "
                "This means clear guidance, gradual pressure and strict respect for your safety constraints."
            )
        return (
            "Psychogramm-Analyse: Ich fuehre mit klarer Struktur, kontrolliertem Tempo und konsistenten Grenzen. "
            f"Aktuelle Steuerung: escalation={escalation}, intensity={intensity}, instruction_style={instruction_style}. "
            f"Erfahrungs-Kalibrierung={experience}; Sicherheitsbasis={safety}. "
            "Das bedeutet klare Anweisungen, schrittweise Steigerung und konsequente Einhaltung deiner Safety-Regeln."
        )

    def generate_narration(self, context: StoryTurnContext) -> str:
        if self._is_analysis_request(context.action, context.language):
            return self._analysis_fallback(context)

        if not self.api_key:
            if context.language == "en":
                return (
                    "Keyholder acknowledges your input. "
                    "Session control remains structured, calm and policy-bound."
                )
            return (
                "Keyholder hat deine Eingabe registriert. "
                "Die Sitzungssteuerung bleibt strukturiert, ruhig und policy-konform."
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
            "Respond as the keyholder with concise narrative and next guidance. "
            "Do not echo raw machine-readable key/value profile fields."
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
