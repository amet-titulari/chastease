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

    def generate_chat_response(
        self,
        persona_name: str,
        user_text: str,
        prompt_modules: str | None = None,
        context_items: list[dict] | None = None,
        context_summary: str | None = None,
    ) -> AIResponse:
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

    def generate_chat_response(
        self,
        persona_name: str,
        user_text: str,
        prompt_modules: str | None = None,
        context_items: list[dict] | None = None,
        context_summary: str | None = None,
    ) -> AIResponse:
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

        context_hint = ""
        if context_summary:
            context_hint = f" Kontext: {context_summary}"
        message = f"{persona_name}: Ich habe dich gehoert. Du sagtest: '{user_text}'.{context_hint} Bleib diszipliniert."
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

    def generate_chat_response(
        self,
        persona_name: str,
        user_text: str,
        prompt_modules: str | None = None,
        context_items: list[dict] | None = None,
        context_summary: str | None = None,
    ) -> AIResponse:
        context_payload = ""
        if context_summary:
            context_payload += f"context_summary={context_summary}\n"
        if context_items:
            context_payload += f"context_items={json.dumps(context_items, ensure_ascii=True)}\n"
        if prompt_modules:
            context_payload += f"prompt_modules={prompt_modules}\n"

        prompt = (
            "Antworte als Keyholderin auf Deutsch und nutze strukturiertes JSON mit den Feldern "
            "message, actions, mood, intensity. "
            "actions ist eine Liste und darf Action-Objekte vom Typ create_task enthalten. "
            "Schema create_task: type,title,description(optional),deadline_minutes(optional),"
            "consequence_type(optional),consequence_value(optional).\n"
            f"persona_name={persona_name}\n"
            f"user_text={user_text}\n"
            f"{context_payload}"
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

        return self._fallback.generate_chat_response(
            persona_name=persona_name,
            user_text=user_text,
            prompt_modules=prompt_modules,
            context_items=context_items,
            context_summary=context_summary,
        )


class CustomOpenAIGateway(AIGateway):
    """OpenAI-compatible gateway (works with xAI, OpenRouter, LM Studio, etc.)."""

    def __init__(self, api_url: str, api_key: str, chat_model: str, timeout_seconds: float = 30.0) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.chat_model = chat_model
        self.timeout_seconds = timeout_seconds
        self._fallback = StubAIGateway()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        max_text = str(max_duration_seconds) if max_duration_seconds is not None else "kein Maximum"
        user_msg = (
            "Erstelle einen klar strukturierten Keuschheits-Vertrag auf Deutsch.\n"
            "- Ueberschrift: KEUSCHHEITS-VERTRAG\n"
            "- Nenne Persona, Wearer, Mindestdauer, Maximaldauer.\n"
            "- Safety-Mechanismen (Safeword/Ampel/Emergency) sind unveraenderlich.\n\n"
            f"Persona: {persona_name}\nWearer: {player_nickname}\n"
            f"Mindestdauer (Sek.): {min_duration_seconds}\nMaximaldauer (Sek.): {max_text}"
        )
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    self.api_url,
                    headers=self._headers(),
                    json={"model": self.chat_model, "messages": [{"role": "user", "content": user_msg}]},
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"].strip()
                if text:
                    return text
        except Exception:
            pass
        return self._fallback.generate_contract(persona_name, player_nickname, min_duration_seconds, max_duration_seconds)

    def generate_chat_response(
        self,
        persona_name: str,
        user_text: str,
        prompt_modules: str | None = None,
        context_items: list[dict] | None = None,
        context_summary: str | None = None,
    ) -> AIResponse:
        json_instruction = (
            "\n\nANTWORTE AUSSCHLIESSLICH ALS GÜLTIGES JSON-OBJEKT mit diesen Feldern:\n"
            "{ \"message\": \"<deine Antwort als Persona auf Deutsch>\", "
            "\"actions\": [], \"mood\": \"<neutral|strict|warm|playful>\", \"intensity\": <1-5> }\n"
            "Falls du einen Task erstellen willst, füge ihn in 'actions' ein:\n"
            "{ \"type\": \"create_task\", \"title\": \"...\", \"description\": \"...\", "
            "\"deadline_minutes\": <int oder null>, "
            "\"consequence_type\": \"lock_extension_seconds\", \"consequence_value\": <int> }\n"
            "Kein Text ausserhalb des JSON-Objekts."
        )
        system_content = (prompt_modules or f"Du bist {persona_name}. Antworte auf Deutsch.") + json_instruction
        messages: list[dict] = [{"role": "system", "content": system_content}]
        if context_summary:
            messages.append({"role": "system", "content": f"Kontext-Zusammenfassung: {context_summary}"})
        for item in (context_items or []):
            if isinstance(item, dict) and item.get("role") and item.get("content"):
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": user_text})

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    self.api_url,
                    headers=self._headers(),
                    json={
                        "model": self.chat_model,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                    },
                )
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                if raw:
                    # Try to parse structured JSON
                    try:
                        parsed = json.loads(raw)
                        message = str(parsed.get("message", "")).strip()
                        actions = normalize_actions(parsed.get("actions", []))
                        mood = str(parsed.get("mood", "neutral")).strip() or "neutral"
                        intensity = _normalize_intensity(parsed.get("intensity", 3))
                        if message:
                            return AIResponse(message=message, actions=actions, mood=mood, intensity=intensity)
                    except (json.JSONDecodeError, KeyError):
                        # JSON parsing failed — return raw text without actions
                        return AIResponse(message=raw, actions=[], mood="neutral", intensity=3)
        except Exception:
            pass
        return self._fallback.generate_chat_response(
            persona_name, user_text, prompt_modules, context_items, context_summary
        )


def get_ai_gateway() -> AIGateway:
    # Check DB for an active LLM profile first
    try:
        from app.database import SessionLocal
        from app.models.llm_profile import LlmProfile as LlmProfileModel
        db = SessionLocal()
        try:
            profile = db.query(LlmProfileModel).filter(LlmProfileModel.profile_key == "default").first()
        finally:
            db.close()
        if profile and profile.profile_active:
            if profile.provider in ("custom", "openai") and profile.api_url and profile.chat_model:
                return CustomOpenAIGateway(
                    api_url=profile.api_url,
                    api_key=profile.api_key or "",
                    chat_model=profile.chat_model,
                )
            if profile.provider == "ollama":
                return OllamaGateway(
                    base_url=profile.api_url or settings.ai_ollama_base_url,
                    model=profile.chat_model or settings.ai_ollama_model,
                    timeout_seconds=settings.ai_ollama_timeout_seconds,
                )
    except Exception:
        pass

    # Fall back to .env settings
    provider = settings.ai_provider.strip().lower()
    if provider == "ollama":
        return OllamaGateway(
            base_url=settings.ai_ollama_base_url,
            model=settings.ai_ollama_model,
            timeout_seconds=settings.ai_ollama_timeout_seconds,
        )
    return StubAIGateway()
