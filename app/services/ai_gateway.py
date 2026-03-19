import json
import logging
import os
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.llm_profile import LlmProfile
from app.schemas.ai_actions import normalize_action_payloads
from app.services.llm_client import LiteLLMClient

logger = logging.getLogger(__name__)

_VALID_MOODS = {"strict", "playful", "teasing", "proud", "caring", "angry"}
_CUSTOM_PROVIDER_ALIASES = {"custom", "xai", "grok", "openai", "openai-compatible"}


def _normalize_openai_base_url(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().rstrip("/")
    if not normalized:
        return None
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")]
    if normalized.endswith("/responses"):
        return normalized[: -len("/responses")]
    return normalized


@dataclass
class AIResponse:
    message: str
    actions: list[dict[str, Any]]
    mood: str
    intensity: int


def _normalize_intensity(value: Any) -> int:
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return 3


def _normalize_mood(value: Any) -> str:
    mood = str(value or "strict").strip().lower()
    return mood if mood in _VALID_MOODS else "strict"


def _normalize_actions(value: Any) -> list[dict[str, Any]]:
    return normalize_action_payloads(value)


def _fallback_contract_text(
    persona_name: str,
    player_nickname: str,
    min_duration_seconds: int,
    max_duration_seconds: int | None,
) -> str:
    max_text = f"bis {max_duration_seconds // 60} Minuten" if max_duration_seconds else "ohne festes Maximum"
    return (
        "KEUSCHHEITS-VERTRAG\n\n"
        f"Persona: {persona_name}\n"
        f"Wearer: {player_nickname}\n"
        f"Mindestdauer: {max(1, int(min_duration_seconds)) // 60} Minuten\n"
        f"Maximaldauer: {max_text}\n\n"
        "Dieser Vertrag gilt als strukturierte Vorlage und wird bis auf Widerruf eingehalten."
    )


def _fallback_chat_response(persona_name: str, user_text: str) -> AIResponse:
    actions: list[dict[str, Any]] = []
    lowered = user_text.lower()
    if "aufgabe" in lowered or "task" in lowered:
        minutes_match = re.search(r"(\d+)\s*min", lowered)
        deadline_minutes = int(minutes_match.group(1)) if minutes_match else None
        quantity_match = re.search(r"(\d+)\s+([a-zA-ZäöüÄÖÜß]+)", user_text)
        title = "Neue Aufgabe"
        if quantity_match:
            title = f"{quantity_match.group(1)} {quantity_match.group(2)}"
        action: dict[str, Any] = {
            "type": "create_task",
            "title": title,
            "description": user_text.strip() or "Vom Stub erzeugte Aufgabe.",
        }
        if deadline_minutes:
            action["deadline_minutes"] = deadline_minutes
        actions.append(action)

    return AIResponse(
        message=f"{persona_name}: Ich habe dich gehoert. {user_text}".strip(),
        actions=actions,
        mood="strict",
        intensity=3,
    )


class AIGateway:
    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        raise NotImplementedError

    def generate_chat_response(self, *args, **kwargs) -> AIResponse:
        raise NotImplementedError


class StubAIGateway(AIGateway):
    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        return _fallback_contract_text(
            persona_name=persona_name,
            player_nickname=player_nickname,
            min_duration_seconds=min_duration_seconds,
            max_duration_seconds=max_duration_seconds,
        )

    def generate_chat_response(
        self,
        persona_name: str,
        user_text: str,
        **_: Any,
    ) -> AIResponse:
        return _fallback_chat_response(persona_name=persona_name, user_text=user_text)


class OllamaGateway(AIGateway):
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.provider = "ollama"
        self.llm_client = LiteLLMClient(timeout_seconds=timeout_seconds)

    def _contract_messages(self, prompt: str) -> list[dict[str, str]]:
        return [{"role": "user", "content": prompt}]

    def _chat_prompt(
        self,
        persona_name: str,
        user_text: str,
        prompt_modules: str | None,
        context_items: list[dict[str, Any]] | None,
        context_summary: str,
    ) -> str:
        prompt_parts = []
        if prompt_modules:
            prompt_parts.append(prompt_modules)
        if context_summary:
            prompt_parts.append(f"Kontext: {context_summary}")
        if context_items:
            for item in context_items:
                content = item.get("content")
                if content:
                    prompt_parts.append(str(content))
        prompt_parts.append(
            "Antworte als JSON mit den Feldern message, actions, mood und intensity. "
            "Wenn du eine Aufgabe vergibst oder der Nutzer explizit nach einer Aufgabe fragt, muss in actions mindestens eine create_task-Action stehen. "
            "Wenn sich Szene, Beziehungsdynamik oder Protokollregeln merklich veraendern, darfst du zusaetzlich eine update_roleplay_state-Action senden."
        )
        prompt_parts.append(f"Persona: {persona_name}")
        prompt_parts.append(f"User: {user_text}")
        return "\n\n".join(prompt_parts)

    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        prompt = (
            "Erstelle einen KEUSCHHEITS-VERTRAG auf Deutsch.\n"
            f"Persona: {persona_name}\n"
            f"Wearer: {player_nickname}\n"
            f"Mindestdauer in Sekunden: {min_duration_seconds}\n"
            f"Maximaldauer in Sekunden: {max_duration_seconds or 0}"
        )
        try:
            content = self.llm_client.complete_text(
                provider=self.provider,
                model=self.model,
                messages=self._contract_messages(prompt),
                api_base=self.base_url,
            )
            if content:
                return content
        except Exception:
            logger.exception("LiteLLM Ollama contract generation failed")

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
            response.raise_for_status()
            data = response.json()
            text = str(data.get("response") or "").strip()
            if text:
                return text
        except Exception:
            logger.exception("Ollama contract generation failed")

        return StubAIGateway().generate_contract(
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
        context_items: list[dict[str, Any]] | None = None,
        context_summary: str = "",
        **_: Any,
    ) -> AIResponse:
        prompt = self._chat_prompt(
            persona_name=persona_name,
            user_text=user_text,
            prompt_modules=prompt_modules,
            context_items=context_items,
            context_summary=context_summary,
        )

        try:
            content = self.llm_client.complete_text(
                provider=self.provider,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_base=self.base_url,
                response_format={"type": "json_object"},
            )
            payload = json.loads(content)
            return AIResponse(
                message=str(payload.get("message") or f"{persona_name}: {user_text}").strip(),
                actions=_normalize_actions(payload.get("actions", [])),
                mood=_normalize_mood(payload.get("mood")),
                intensity=_normalize_intensity(payload.get("intensity")),
            )
        except Exception:
            logger.exception("LiteLLM Ollama chat generation failed")

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
            response.raise_for_status()
            raw_response = response.json().get("response")
            payload = json.loads(raw_response)
            return AIResponse(
                message=str(payload.get("message") or f"{persona_name}: {user_text}").strip(),
                actions=_normalize_actions(payload.get("actions", [])),
                mood=_normalize_mood(payload.get("mood")),
                intensity=_normalize_intensity(payload.get("intensity")),
            )
        except Exception:
            logger.exception("Ollama chat generation failed")
            return StubAIGateway().generate_chat_response(
                persona_name=persona_name,
                user_text=user_text,
            )


class CustomOpenAIGateway(AIGateway):
    def __init__(self, profile: Any, timeout_seconds: float = 30.0):
        self.api_base = _normalize_openai_base_url(profile.api_url) or "https://api.x.ai/v1"
        self.api_key = profile.api_key
        self.chat_model = profile.chat_model or "grok-beta"
        self.timeout_seconds = timeout_seconds
        self.provider = "xai" if "x.ai" in self.api_base else "openai-compatible"
        self.llm_client = LiteLLMClient(timeout_seconds=timeout_seconds)

    def _contract_messages(self, prompt: str) -> list[dict[str, str]]:
        return [
            {
                "role": "user",
                "content": (
                    "Formuliere den folgenden Vertrag sprachlich aus und gib nur den Vertragstext zurueck:\n\n"
                    f"{prompt}"
                ),
            }
        ]

    def _chat_messages(
        self,
        user_text: str,
        prompt_modules: str | None,
        context_items: list[dict[str, Any]] | None,
        context_summary: str,
        image_bytes: bytes | None,
        image_filename: str | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if prompt_modules:
            messages.append({"role": "system", "content": prompt_modules})
        if context_summary:
            messages.append({"role": "system", "content": f"Kontext: {context_summary}"})
        if context_items:
            for item in context_items:
                content = item.get("content")
                if content:
                    messages.append({"role": item.get("role", "system"), "content": str(content)})

        user_content: Any = user_text
        if image_bytes:
            import base64

            mime_type = "image/jpeg"
            if image_filename and "." in image_filename:
                extension = image_filename.rsplit(".", 1)[1].lower()
                if extension == "png":
                    mime_type = "image/png"
                elif extension == "webp":
                    mime_type = "image/webp"
            user_content = [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
                    },
                },
            ]

        messages.append(
            {
                "role": "system",
                "content": (
                    "Antworte nur als JSON mit message, actions, mood, intensity. "
                    "Wenn du eine Aufgabe vergibst oder der Nutzer explizit nach einer Aufgabe fragt, muss in actions mindestens eine create_task-Action stehen. "
                    "Wenn sich Szene, Beziehung oder Protokollaenderungen ergeben, darfst du eine update_roleplay_state-Action mitsenden."
                ),
            }
        )
        messages.append({"role": "user", "content": user_content})
        return messages

    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        prompt = _fallback_contract_text(
            persona_name=persona_name,
            player_nickname=player_nickname,
            min_duration_seconds=min_duration_seconds,
            max_duration_seconds=max_duration_seconds,
        )
        try:
            content = self.llm_client.complete_text(
                provider=self.provider,
                model=self.chat_model,
                messages=self._contract_messages(prompt),
                api_base=self.api_base,
                api_key=self.api_key,
            )
            if content:
                return content
        except Exception:
            logger.exception("LiteLLM contract generation failed")

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.chat_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": (
                                    "Formuliere den folgenden Vertrag sprachlich aus und gib nur den Vertragstext zurueck:\n\n"
                                    f"{prompt}"
                                ),
                            }
                        ],
                    },
                )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if isinstance(content, str) and content.strip():
                return content.strip()
        except Exception:
            logger.exception("Custom OpenAI contract generation failed")
        return prompt

    def generate_chat_response(
        self,
        persona_name: str,
        user_text: str,
        prompt_modules: str | None = None,
        context_items: list[dict[str, Any]] | None = None,
        context_summary: str = "",
        image_bytes: bytes | None = None,
        image_filename: str | None = None,
        **_: Any,
    ) -> AIResponse:
        messages = self._chat_messages(
            user_text=user_text,
            prompt_modules=prompt_modules,
            context_items=context_items,
            context_summary=context_summary,
            image_bytes=image_bytes,
            image_filename=image_filename,
        )

        try:
            content = self.llm_client.complete_text(
                provider=self.provider,
                model=self.chat_model,
                messages=messages,
                api_base=self.api_base,
                api_key=self.api_key,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(content)
            return AIResponse(
                message=str(parsed.get("message") or f"{persona_name}: {user_text}").strip(),
                actions=_normalize_actions(parsed.get("actions", [])),
                mood=_normalize_mood(parsed.get("mood")),
                intensity=_normalize_intensity(parsed.get("intensity")),
            )
        except Exception:
            logger.exception("LiteLLM chat generation failed")

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.chat_model,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                    },
                )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Unsupported content payload")
            parsed = json.loads(content)
            return AIResponse(
                message=str(parsed.get("message") or f"{persona_name}: {user_text}").strip(),
                actions=_normalize_actions(parsed.get("actions", [])),
                mood=_normalize_mood(parsed.get("mood")),
                intensity=_normalize_intensity(parsed.get("intensity")),
            )
        except Exception:
            logger.exception("Custom OpenAI chat generation failed")
            return StubAIGateway().generate_chat_response(
                persona_name=persona_name,
                user_text=user_text,
            )


def _build_session_profile(session_obj: Any) -> Any | None:
    if session_obj is None:
        return None
    if not getattr(session_obj, "llm_profile_active", False):
        return None
    api_url = getattr(session_obj, "llm_api_url", None)
    api_key = getattr(session_obj, "llm_api_key", None)
    if not api_url or not api_key:
        return None
    return SimpleNamespace(
        api_url=_normalize_openai_base_url(api_url),
        api_key=api_key,
        chat_model=getattr(session_obj, "llm_chat_model", None),
        vision_model=getattr(session_obj, "llm_vision_model", None),
    )


def _build_env_profile() -> Any | None:
    api_key = settings.ai_api_key or os.getenv("XAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    api_url = _normalize_openai_base_url(settings.ai_api_url) or "https://api.x.ai/v1"
    chat_model = settings.ai_chat_model or "grok-beta"
    vision_model = settings.ai_vision_model or chat_model
    if not api_key:
        return None
    return SimpleNamespace(
        api_url=api_url,
        api_key=api_key,
        chat_model=chat_model,
        vision_model=vision_model,
    )


def _load_default_profile() -> LlmProfile | None:
    with SessionLocal() as db:
        return (
            db.query(LlmProfile)
            .filter(LlmProfile.profile_active == True)
            .order_by(LlmProfile.id.asc())
            .first()
        )


def get_ai_gateway(session_obj: Any | None = None) -> AIGateway:
    session_profile = _build_session_profile(session_obj)
    if session_profile is not None:
        return CustomOpenAIGateway(session_profile)

    default_profile = _load_default_profile()
    if default_profile and default_profile.api_url and default_profile.api_key:
        return CustomOpenAIGateway(default_profile)

    provider = str(settings.ai_provider or "stub").strip().lower()
    if provider in _CUSTOM_PROVIDER_ALIASES:
        env_profile = _build_env_profile()
        if env_profile is not None:
            return CustomOpenAIGateway(env_profile)
    if provider == "ollama":
        return OllamaGateway(
            base_url=settings.ai_ollama_base_url,
            model=settings.ai_ollama_model,
            timeout_seconds=float(settings.ai_ollama_timeout_seconds),
        )

    return StubAIGateway()
