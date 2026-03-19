from typing import Any

from litellm import completion


class LiteLLMClient:
    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds

    def complete_text(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        api_base: str | None = None,
        api_key: str | None = None,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._qualify_model(provider=provider, model=model),
            "messages": messages,
            "timeout": self.timeout_seconds,
        }
        if api_base:
            payload["api_base"] = api_base
        if api_key:
            payload["api_key"] = api_key
        if response_format is not None:
            payload["response_format"] = response_format
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        response = completion(**payload)
        return self._extract_text(response)

    @staticmethod
    def _qualify_model(provider: str, model: str) -> str:
        normalized_provider = (provider or "").strip().lower()
        if normalized_provider in {"xai", "grok"}:
            return model if "/" in model else f"xai/{model}"
        if normalized_provider == "ollama":
            return model if "/" in model else f"ollama/{model}"
        return model

    @staticmethod
    def _extract_text(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if choices is None and isinstance(response, dict):
            choices = response.get("choices")
        if not choices:
            raise ValueError("No choices in LiteLLM response")

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None and isinstance(first_choice, dict):
            message = first_choice.get("message")
        if message is None:
            raise ValueError("No message in LiteLLM response")

        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text") or ""))
            content = "\n".join(part for part in text_parts if part)
        if not isinstance(content, str):
            raise ValueError("Unsupported LiteLLM content payload")
        return content.strip()