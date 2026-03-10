from dataclasses import dataclass

import httpx

from app.config import settings


@dataclass
class AIResponse:
    message: str
    actions: list[dict]
    mood: str
    intensity: int


class AIGateway:
    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        raise NotImplementedError


class StubAIGateway(AIGateway):
    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        max_duration_text = str(max_duration_seconds) if max_duration_seconds is not None else "kein Maximum"
        return (
            "KEUSCHHEITS-VERTRAG\n"
            f"Keyholder-Persona: {persona_name}\n"
            f"Wearer: {player_nickname}\n"
            f"Mindestdauer (Sek.): {min_duration_seconds}\n"
            f"Maximaldauer (Sek.): {max_duration_text}\n"
            "\n"
            "Dieser Entwurf wird mit der digitalen Signatur bindend.\n"
            "Sicherheitsmechanismen (Safeword/Ampel/Emergency) bleiben unveraenderlich."
        )


class OllamaGateway(AIGateway):
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._fallback = StubAIGateway()

    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        max_duration_text = str(max_duration_seconds) if max_duration_seconds is not None else "kein Maximum"
        prompt = (
            "Erstelle einen klar strukturierten Keuschheits-Vertrag auf Deutsch.\n"
            "Regeln:\n"
            "- Nutze die Ueberschrift KEUSCHHEITS-VERTRAG.\n"
            "- Nenne Persona, Wearer, Mindestdauer und Maximaldauer.\n"
            "- Weisen auf bindende Signatur hin.\n"
            "- Safety-Mechanismen (Safeword/Ampel/Emergency) sind unveraenderlich.\n\n"
            f"Persona: {persona_name}\n"
            f"Wearer: {player_nickname}\n"
            f"Mindestdauer (Sek.): {min_duration_seconds}\n"
            f"Maximaldauer (Sek.): {max_duration_text}\n"
        )

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                text = payload.get("response", "")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        except Exception:
            # Keep session flow available even if Ollama is not running.
            pass

        return self._fallback.generate_contract(
            persona_name=persona_name,
            player_nickname=player_nickname,
            min_duration_seconds=min_duration_seconds,
            max_duration_seconds=max_duration_seconds,
        )


def get_ai_gateway() -> AIGateway:
    provider = settings.ai_provider.strip().lower()
    if provider == "ollama":
        return OllamaGateway(
            base_url=settings.ai_ollama_base_url,
            model=settings.ai_ollama_model,
            timeout_seconds=settings.ai_ollama_timeout_seconds,
        )
    return StubAIGateway()
