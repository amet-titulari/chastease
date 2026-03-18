# app/services/ai_gateway.py
# ──────────────────────────────────────────────────────────────────────────────
# 2026-03 – optimierte Grok/xAI + OpenAI-kompatible Implementierung
# ──────────────────────────────────────────────────────────────────────────────

import base64
import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import httpx
from pydantic import ValidationError

from app.config import settings
from app.models.ai import LLMProfile
# Annahme: Deine bestehenden Normalisierungsfunktionen sind importierbar
from .normalizers import normalize_actions, normalize_mood, normalize_intensity

logger = logging.getLogger(__name__)

@dataclass
class AIResponse:
    message: str
    actions: List[Dict[str, Any]]
    mood: str
    intensity: int

class AIGateway:
    async def generate_chat_response(self, *args, **kwargs) -> AIResponse:
        raise NotImplementedError

class StubAIGateway(AIGateway):
    # Deine bestehende Stub-Implementierung bleibt erhalten
    ...

class CustomOpenAIGateway(AIGateway):
    """Grok/xAI optimierter Adapter – strict JSON, Vision-fähig, robust"""

    def __init__(self, profile: LLMProfile):
        self.api_base = (profile.api_url or "https://api.x.ai/v1").rstrip("/")
        self.api_key = profile.api_key
        self.chat_model = profile.chat_model or "grok-beta"
        self.vision_model = profile.vision_model or self.chat_model
        self.timeout = httpx.Timeout(90.0)

        if not self.api_key:
            raise ValueError("Kein API-Key in LLMProfile gefunden")

        self.client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout
        )

    def _strict_system_prompt(self, persona_prompt: str, safety_rules: str) -> str:
        schema = """{
  "type": "object",
  "properties": {
    "message": {
      "type": "string",
      "description": "Antwort an den Wearer – immer auf Deutsch, immersiv, in-character"
    },
    "actions": {
      "type": "array",
      "items": {
        "type": "object",
        "oneOf": [
          {"$ref": "#/definitions/create_task"},
          {"$ref": "#/definitions/update_task"},
          {"$ref": "#/definitions/fail_task"}
        ]
      },
      "description": "Nur Aktionen die wirklich passen – sonst leeres Array []"
    },
    "mood": {"enum": ["strict","playful","teasing","proud","caring","angry"]},
    "intensity": {"type": "integer", "minimum":1, "maximum":5}
  },
  "required": ["message", "actions", "mood", "intensity"],
  "definitions": {
    "create_task": {
      "type": "object",
      "properties": {
        "type": {"const": "create_task"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "deadline_minutes": {"type": ["integer","null"]},
        "requires_verification": {"type": "boolean", "default": false},
        "verification_criteria": {"type": ["string","null"]}
      },
      "required": ["type","title","description"]
    },
    "update_task": { ... },  // analog
    "fail_task":   { ... }
  }
}"""

        return f"""{persona_prompt}

{safety_rules}

=== STRENGES FORMAT ===
Antworte **ausschließlich** mit einem einzigen, gültigen JSON-Objekt.
Kein einleitender Text, kein ```json, kein Erklärungstext danach.
Das JSON muss 100% dem obigen Schema entsprechen.

Wenn du keine Aktion auslösen möchtest → "actions": []
"""

    async def generate_chat_response(
        self,
        messages: List[Dict[str, Any]],
        context_summary: str = "",
        image_data: Optional[bytes] = None,
        image_mime: str = "image/jpeg",
        **kwargs
    ) -> AIResponse:
        # Baue finale Messages
        full_messages = messages.copy()

        # Strict System-Prompt am Anfang
        strict_system = self._strict_system_prompt(
            persona_prompt=kwargs.get("persona_prompt", ""),
            safety_rules=kwargs.get("safety_rules", "")
        )
        full_messages.insert(0, {"role": "system", "content": strict_system})

        if context_summary:
            full_messages.insert(1, {"role": "system", "content": f"← Letzte Events (Zusammenfassung): {context_summary}"})

        # Vision hinzufügen (falls Bild vorhanden)
        last_msg = full_messages[-1]
        if image_data and last_msg["role"] == "user":
            base64_img = base64.b64encode(image_data).decode("utf-8")
            last_msg["content"] = [
                {"type": "text", "text": last_msg["content"]},
                {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{base64_img}"}}
            ]

        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.chat_model,
                    "messages": full_messages,
                    "temperature": 0.65,
                    "max_tokens": 2048,
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                logger.error("Grok hat kein valides JSON zurückgegeben: %s", content[:200])
                return AIResponse("Entschuldige, ich hatte einen technischen Moment…", [], "strict", 3)

            return AIResponse(
                message=data.get("message", "…"),
                actions=normalize_actions(data.get("actions", [])),
                mood=normalize_mood(data.get("mood", "strict")),
                intensity=normalize_intensity(data.get("intensity", 3))
            )

        except httpx.HTTPStatusError as e:
            logger.error("Grok API Fehler: %s – %s", e.response.status_code, e.response.text)
            return AIResponse("Momentan gibt es ein Problem mit meiner Leitung…", [], "caring", 2)
        except Exception as e:
            logger.exception("Unerwarteter Fehler in Grok-Gateway")
            return StubAIGateway().generate_chat_response(...)  # Fallback
