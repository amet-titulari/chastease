from dataclasses import dataclass
import json
import re

import httpx

from app.config import settings


@dataclass
class AIResponse:
    message: str
    actions: list[dict]
    mood: str
    intensity: int


def _normalize_create_task_action(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None

    title = str(raw.get("title", "")).strip()
    if not title:
        return None

    normalized: dict = {
        "type": "create_task",
        "title": title[:200],
    }

    description = raw.get("description")
    if description is not None:
        description_text = str(description).strip()
        if description_text:
            normalized["description"] = description_text[:2000]

    deadline_minutes = raw.get("deadline_minutes")
    if isinstance(deadline_minutes, int):
        if deadline_minutes > 0:
            normalized["deadline_minutes"] = deadline_minutes
    else:
        try:
            coerced = int(deadline_minutes)
            if coerced > 0:
                normalized["deadline_minutes"] = coerced
        except Exception:
            pass

    consequence_type = raw.get("consequence_type")
    if isinstance(consequence_type, str) and consequence_type.strip() in {"lock_extension_seconds"}:
        normalized["consequence_type"] = consequence_type.strip()

    consequence_value = raw.get("consequence_value")
    if isinstance(consequence_value, int):
        if consequence_value > 0:
            normalized["consequence_value"] = consequence_value
    else:
        try:
            coerced = int(consequence_value)
            if coerced > 0:
                normalized["consequence_value"] = coerced
        except Exception:
            pass

    return normalized


def normalize_actions(raw_actions) -> list[dict]:
    if not isinstance(raw_actions, list):
        return []

    normalized: list[dict] = []
    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "create_task":
            parsed = _normalize_create_task_action(item)
            if parsed is not None:
                normalized.append(parsed)
    return normalized


def _normalize_intensity(value) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = 3
    return max(1, min(5, parsed))


class AIGateway:
    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        raise NotImplementedError

    def generate_chat_response(self, persona_name: str, user_text: str) -> AIResponse:
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

    def generate_chat_response(self, persona_name: str, user_text: str) -> AIResponse:
        lowered = user_text.lower()
        actions: list[dict] = []

        if "aufgabe" in lowered or "task" in lowered:
            title = "Disziplin-Check"
            match = re.search(r"(?:aufgabe|task)\s*[:\-]\s*(.+)", user_text, flags=re.IGNORECASE)
            if match:
                title = match.group(1).strip()[:200] or title

            deadline_minutes = None
            deadline_match = re.search(r"(\d+)\s*(?:min|minute|minutes)", lowered)
            if deadline_match:
                deadline_minutes = max(1, int(deadline_match.group(1)))

            actions.append(
                {
                    "type": "create_task",
                    "title": title,
                    "description": "Automatisch aus Chat-Anfrage erzeugt.",
                    "deadline_minutes": deadline_minutes,
                    "consequence_type": "lock_extension_seconds",
                    "consequence_value": 300,
                }
            )

        message = f"{persona_name}: Ich habe dich gehoert. Du sagtest: '{user_text}'. Bleib diszipliniert."
        if actions:
            message += " Ich habe dir eine passende Aufgabe gesetzt."

        return AIResponse(
            message=message,
            actions=normalize_actions(actions),
            mood="strict",
            intensity=3,
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

    def generate_chat_response(self, persona_name: str, user_text: str) -> AIResponse:
        prompt = (
            "Antworte als Keyholderin auf Deutsch und nutze strukturiertes JSON mit den Feldern "
            "message, actions, mood, intensity. "
            "actions ist eine Liste und darf Action-Objekte vom Typ create_task enthalten. "
            "Schema create_task: type,title,description(optional),deadline_minutes(optional),"
            "consequence_type(optional),consequence_value(optional).\n"
            f"persona_name={persona_name}\n"
            f"user_text={user_text}\n"
        )

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                                "actions": {"type": "array"},
                                "mood": {"type": "string"},
                                "intensity": {"type": "integer"},
                            },
                            "required": ["message", "actions", "mood", "intensity"],
                        },
                    },
                )
                response.raise_for_status()
                payload = response.json()
                raw = payload.get("response", "")
                if isinstance(raw, str) and raw.strip():
                    parsed = json.loads(raw)
                    message = str(parsed.get("message", "")).strip()
                    actions = normalize_actions(parsed.get("actions", []))
                    mood = str(parsed.get("mood", "neutral")).strip() or "neutral"
                    intensity = _normalize_intensity(parsed.get("intensity", 3))
                    if message:
                        return AIResponse(
                            message=message,
                            actions=actions,
                            mood=mood,
                            intensity=intensity,
                        )
        except Exception:
            pass

        return self._fallback.generate_chat_response(persona_name=persona_name, user_text=user_text)


def get_ai_gateway() -> AIGateway:
    provider = settings.ai_provider.strip().lower()
    if provider == "ollama":
        return OllamaGateway(
            base_url=settings.ai_ollama_base_url,
            model=settings.ai_ollama_model,
            timeout_seconds=settings.ai_ollama_timeout_seconds,
        )
    return StubAIGateway()
