import httpx
from typing import Any
from urllib.parse import urlparse

from .base import StoryTurnContext


class OpenAIAdapter:
    """First OpenAI adapter with deterministic fallback for local/dev usage."""

    def __init__(self, model: str, api_key: str = ""):
        self.model = model
        self.api_key = api_key

    @staticmethod
    def _post_json_once(
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: httpx.Timeout,
    ) -> httpx.Response:
        # Use a fresh client per request to avoid connection-reuse issues (HTTP 421).
        # This mirrors the behavior in the legacy app where requests were isolated.
        with httpx.Client(
            timeout=timeout,
            http2=False,
            limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
        ) as client:
            return client.post(url, headers=headers, json=payload)

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
            return any(token in text for token in ["psychogram", "profile"])
        return any(token in text for token in ["psychogram", "profil"])

    @staticmethod
    def _wants_image_review(action: str) -> bool:
        text = action.lower()
        return any(token in text for token in ["bild", "image", "foto", "photo", "screenshot", "screen"])

    @staticmethod
    def _has_image_attachment(attachments: list[dict[str, Any]] | None) -> bool:
        for item in attachments or []:
            mime_type = str(item.get("type", item.get("mime_type", ""))).lower()
            data_url = str(item.get("data_url", ""))
            if mime_type.startswith("image/") and data_url.startswith("data:image/"):
                return True
        return False

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

    @staticmethod
    def _candidate_llm_urls(raw_url: str) -> list[tuple[str, str]]:
        url = (raw_url or "").strip()
        if not url:
            return []
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else url.rstrip("/")
        base_path = (parsed.path or "").strip()
        candidates: list[tuple[str, str]] = []
        if base_path:
            kind = "responses" if base_path.endswith("/responses") else "chat"
            # If the user configured an explicit endpoint path, trust it to avoid double-timeouts.
            candidates.append((url, kind))
            return candidates
        for endpoint, kind in [
            (f"{base}/v1/chat/completions", "chat"),
            (f"{base}/chat/completions", "chat"),
            (f"{base}/api/chat/completions", "chat"),
            (f"{base}/v1/responses", "responses"),
            (base, "chat"),
        ]:
            if (endpoint, kind) not in candidates:
                candidates.append((endpoint, kind))
        return candidates

    @staticmethod
    def _extract_reply_text(data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: list[str] = []
                for chunk in content:
                    if isinstance(chunk, dict) and chunk.get("type") == "text":
                        text = str(chunk.get("text") or "").strip()
                        if text:
                            parts.append(text)
                if parts:
                    return "\n".join(parts).strip()
            text_value = choices[0].get("text")
            if isinstance(text_value, str):
                return text_value.strip()
        output_text = data.get("output_text")
        if isinstance(output_text, str):
            return output_text.strip()
        return ""

    def generate_narration(self, context: StoryTurnContext) -> str:
        if self._is_analysis_request(context.action, context.language):
            return self._analysis_fallback(context)

        if self._wants_image_review(context.action):
            if context.language == "en":
                return (
                    "I need an actual image attachment to analyze it. "
                    "Please upload a clear image and send again."
                )
            return (
                "Ich brauche einen echten Bild-Anhang fuer die Analyse. "
                "Bitte lade ein klares Bild hoch und sende erneut."
            )

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
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        if not api_url or not api_key or not chat_model:
            return self.generate_narration(context)

        system_prompt = (
            "You are a safe roleplay keyholder assistant. "
            "Respect explicit hard limits and safety constraints. "
            "Never invent facts about files/images you cannot see. "
            "If an attachment is missing or unreadable, say so clearly and ask for a better upload. "
            "Keep answers concise and operational. "
            "When proposing a tool action, append exactly one machine line at the very end in this format: "
            "[[REQUEST:<action_type>|<json_payload>]]. "
            "Use compact valid JSON on one line. "
            "Do not use [Suggest: ...] and do not use free-text pseudo actions."
            "Payload rules are strict: "
            "for add_time/reduce_time always send {\"seconds\": <positive_integer>}; "
            "for pause_timer/unpause_timer always send {} and no duration fields. "
            "For image_verification send a payload with at least "
            "{\"request\": \"...\", \"verification_instruction\": \"...\"}. "
            "Before requesting image_verification, explain briefly what image should be provided and how you will verify it."
        )
        if behavior_prompt.strip():
            system_prompt = f"{system_prompt}\n\nBehavior profile:\n{behavior_prompt.strip()}"

        attachment_lines = []
        attachment_content: list[dict[str, Any]] = []
        for item in attachments or []:
            name = str(item.get("name", "file"))
            mime_type = str(item.get("type", item.get("mime_type", "application/octet-stream")))
            attachment_lines.append(f"- {name} ({mime_type})")
            data_url = item.get("data_url")
            if isinstance(data_url, str) and data_url.startswith("data:image/"):
                attachment_content.append({"type": "image_url", "image_url": {"url": data_url}})

        attachment_summary = "\n".join(attachment_lines) if attachment_lines else "- none"
        user_prompt = (
            f"Session: {context.session_id}\n"
            f"Psychogram summary: {context.psychogram_summary}\n"
            f"Wearer action: {context.action}\n"
            f"Attachments:\n{attachment_summary}\n"
            f"Language: {context.language}\n"
            "Respond as the keyholder with concise narrative and next guidance. "
            "Do not echo raw machine-readable key/value profile fields."
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Connection": "close",
        }
        user_message: dict[str, Any] = {"role": "user", "content": user_prompt}
        if attachment_content:
            user_message = {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}, *attachment_content],
            }
        payload = {
            "model": chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                user_message,
            ],
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 350,
        }
        responses_payload = {
            "model": chat_model,
            "input": user_prompt,
            "temperature": 0.3,
            "max_output_tokens": 350,
        }

        has_image_payload = bool(attachment_content)
        timeout = (
            httpx.Timeout(connect=5.0, read=35.0, write=20.0, pool=5.0)
            if has_image_payload
            else httpx.Timeout(connect=5.0, read=25.0, write=20.0, pool=5.0)
        )
        retry_timeout = (
            httpx.Timeout(connect=6.0, read=50.0, write=25.0, pool=6.0)
            if has_image_payload
            else httpx.Timeout(connect=6.0, read=35.0, write=20.0, pool=6.0)
        )
        try:
            candidates = self._candidate_llm_urls(api_url)
            last_error = "unknown"
            attempted: list[str] = []
            for target_url, kind in candidates:
                attempts = (1, 2) if has_image_payload else (1,)
                for attempt in attempts:
                    attempted.append(f"{target_url} ({kind})")
                    request_payload = dict(responses_payload if kind == "responses" else payload)
                    token_key = "max_output_tokens" if kind == "responses" else "max_tokens"
                    if attempt == 2 and token_key in request_payload:
                        request_payload[token_key] = max(128, int(request_payload[token_key] * 0.6))
                    try:
                        response = self._post_json_once(
                            url=target_url,
                            headers=headers,
                            payload=request_payload,
                            timeout=timeout,
                        )
                        if response.status_code in (404, 405):
                            last_error = f"{response.status_code} from {target_url}"
                            break
                        response.raise_for_status()
                        data = response.json()
                        text = self._extract_reply_text(data)
                        if text:
                            return text
                        last_error = f"empty response from {target_url}"
                    except httpx.TimeoutException:
                        last_error = f"timeout at {target_url}"
                        if attempt == 1:
                            continue
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code if exc.response is not None else "unknown"
                        body = (exc.response.text[:220] if exc.response is not None else "").strip()
                        last_error = f"http {status} at {target_url}{(': ' + body) if body else ''}"
                        # Auth/quota/compatibility failures should fail fast.
                        # Keep 421 as fallback-eligible because some providers require switching chat<->responses.
                        if status in (400, 401, 402, 403, 422, 429):
                            raise RuntimeError(last_error)
                        break
                    except Exception as exc:
                        last_error = f"{exc.__class__.__name__} at {target_url}"
                        break
            attempted_hint = ", ".join(dict.fromkeys(attempted))
            raise RuntimeError(f"{last_error}; tried={attempted_hint}")
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            if context.language == "en":
                return (
                    f"Provider rejected the request (HTTP {status}). "
                    "Please verify endpoint/model/API key compatibility."
                )
            return (
                f"Der Provider hat die Anfrage abgelehnt (HTTP {status}). "
                "Bitte pruefe Endpoint/Modell/API-Key-Kompatibilitaet."
            )
        except RuntimeError as exc:
            if context.language == "en":
                return (
                    f"Provider request failed ({str(exc)}). "
                    "Please verify endpoint/model/API key compatibility."
                )
            return (
                f"Provider-Anfrage fehlgeschlagen ({str(exc)}). "
                "Bitte Endpoint/Modell/API-Key-Kompatibilitaet pruefen."
            )
        except httpx.TimeoutException:
            try:
                response = self._post_json_once(
                    url=api_url,
                    headers=headers,
                    payload=payload,
                    timeout=retry_timeout,
                )
                response.raise_for_status()
                data = response.json()
                text = self._extract_reply_text(data)
                return text if text else "Provider timeout."
            except Exception:
                if context.language == "en":
                    return (
                        "Provider timeout. Please retry; for image analysis use a smaller image."
                    )
                return (
                    "Provider-Timeout. Bitte erneut versuchen; fuer Bildanalyse ggf. kleineres Bild nutzen."
                )
        except Exception:
            if self._wants_image_review(context.action):
                if self._has_image_attachment(attachments):
                    if context.language == "en":
                        return (
                            "Image analysis is currently unavailable (provider timeout/error). "
                            "Please retry in a moment."
                        )
                    return (
                        "Die Bildanalyse ist aktuell nicht verfuegbar (Provider Timeout/Fehler). "
                        "Bitte versuche es gleich erneut."
                    )
                if context.language == "en":
                    return (
                        "I cannot see an image attachment. Please upload an image file and resend."
                    )
                return (
                    "Ich kann keinen Bild-Anhang sehen. Bitte lade ein Bild hoch und sende erneut."
                )
            if context.language == "en":
                return (
                    "LLM request failed unexpectedly. Please verify provider configuration and retry."
                )
            return (
                "LLM-Anfrage unerwartet fehlgeschlagen. Bitte Provider-Konfiguration pruefen und erneut senden."
            )
