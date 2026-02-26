import httpx
import logging
import random
import time
from datetime import datetime, UTC
from typing import Any
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from .base import StoryTurnContext

logger = logging.getLogger(__name__)


class OpenAIAdapter:
    """First OpenAI adapter with deterministic fallback for local/dev usage."""

    def __init__(self, model: str, api_key: str = "", config: Any | None = None):
        self.model = model
        self.api_key = api_key
        self.strict_explicit_endpoint = bool(getattr(config, "LLM_STRICT_EXPLICIT_ENDPOINT", True))
        self.chat_max_tokens = int(getattr(config, "LLM_CHAT_MAX_TOKENS", 220))
        self.chat_retry_attempts = int(getattr(config, "LLM_CHAT_RETRY_ATTEMPTS", 1))
        self.chat_timeout_connect = float(getattr(config, "LLM_CHAT_TIMEOUT_CONNECT", 3.0))
        self.chat_timeout_read = float(getattr(config, "LLM_CHAT_TIMEOUT_READ", 10.0))
        self.chat_timeout_write = float(getattr(config, "LLM_CHAT_TIMEOUT_WRITE", 10.0))
        self.chat_timeout_pool = float(getattr(config, "LLM_CHAT_TIMEOUT_POOL", 3.0))

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
    def _candidate_llm_urls(raw_url: str, *, strict_explicit_endpoint: bool = True) -> list[tuple[str, str]]:
        url = (raw_url or "").strip()
        if not url:
            return []
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else url.rstrip("/")
        base_path = (parsed.path or "").strip()
        candidates: list[tuple[str, str]] = []
        if base_path:
            kind = "responses" if base_path.endswith("/responses") else "chat"
            # If an explicit endpoint path is configured, keep it strict unless compatibility fallback is requested.
            candidates.append((url, kind))
            if not strict_explicit_endpoint:
                if kind == "chat":
                    candidates.append((f"{base}/v1/responses", "responses"))
                else:
                    candidates.append((f"{base}/v1/chat/completions", "chat"))
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
    def _retry_delay_seconds(attempt: int, retry_after_header: str | None = None) -> float:
        if retry_after_header:
            raw = str(retry_after_header).strip()
            if raw:
                try:
                    seconds = float(raw)
                    if seconds > 0:
                        return min(seconds, 12.0)
                except ValueError:
                    try:
                        dt = parsedate_to_datetime(raw)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=UTC)
                        wait = (dt - datetime.now(UTC)).total_seconds()
                        if wait > 0:
                            return min(wait, 12.0)
                    except Exception:
                        pass
        base = min(0.5 * (2 ** max(0, attempt - 1)), 4.0)
        jitter = random.uniform(0.0, 0.25)
        return base + jitter

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
                    if isinstance(chunk, dict) and chunk.get("type") in {"text", "output_text", "input_text"}:
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
        output = data.get("output")
        if isinstance(output, list):
            parts: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    parts.append(content.strip())
                    continue
                if not isinstance(content, list):
                    continue
                for chunk in content:
                    if not isinstance(chunk, dict):
                        continue
                    if chunk.get("type") not in {"text", "output_text", "input_text"}:
                        continue
                    text = str(chunk.get("text") or "").strip()
                    if text:
                        parts.append(text)
            if parts:
                return "\n".join(parts).strip()
        return ""

    @staticmethod
    def _is_setup_preview_contract_request(context: StoryTurnContext) -> bool:
        if context.session_id != "setup-preview":
            return False
        action = (context.action or "").lower()
        contract_tokens = (
            "draft contract",
            "vertrags-entwurf",
            "rewrite the contract",
            "schreibe den vertrag",
            "generated chastity contract",
            "keuschheitsvertrag",
            "article 1",
            "artikel 1",
        )
        return any(token in action for token in contract_tokens)

    @staticmethod
    def _is_setup_preview_analysis_request(context: StoryTurnContext) -> bool:
        if context.session_id != "setup-preview":
            return False
        action = (context.action or "").lower()
        return "psychogram" in action

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
            "Action protocol is mandatory and strict. "
            "If your response asks for, approves, schedules, or executes an operational step, "
            "you MUST append exactly one machine line at the very end in this format: "
            "[[REQUEST:<action_type>|<json_payload>]]. "
            "Use compact valid JSON on one line only. "
            "Never output [Suggest: ...], [REQUEST: ...(...)] call-style, or free-text pseudo actions. "
            "If no operational action is intended, output no REQUEST line at all. "
            "Payload rules are strict: "
            "for add_time/reduce_time always send {\"seconds\": <positive_integer>}; "
            "for pause_timer/unpause_timer always send {} and no duration fields. "
            "for hygiene_open/hygiene_close always send a JSON object (at least {\"reason\":\"...\"} when meaningful). "
            "For image_verification send a payload with at least "
            "{\"request\": \"...\", \"verification_instruction\": \"...\"}. "
            "Before requesting image_verification, explain briefly what image should be provided and how you will verify it. "
            "Examples of valid final lines: "
            "[[REQUEST:hygiene_open|{\"reason\":\"hygiene\"}]] "
            "[[REQUEST:add_time|{\"seconds\":900}]] "
            "[[REQUEST:pause_timer|{}]]"
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
        is_setup_contract = self._is_setup_preview_contract_request(context)
        is_setup_analysis = self._is_setup_preview_analysis_request(context)
        max_tokens = 1800 if is_setup_contract else (650 if is_setup_analysis else self.chat_max_tokens)

        payload = {
            "model": chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                user_message,
            ],
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": max_tokens,
        }
        responses_payload = {
            "model": chat_model,
            "input": user_prompt,
            "temperature": 0.3,
            "max_output_tokens": max_tokens,
        }

        has_image_payload = bool(attachment_content)
        if has_image_payload and max_tokens < 320:
            max_tokens = 320
            payload["max_tokens"] = max_tokens
            responses_payload["max_output_tokens"] = max_tokens
        if has_image_payload:
            attempt_timeouts = [
                httpx.Timeout(connect=5.0, read=35.0, write=20.0, pool=5.0),
                httpx.Timeout(connect=6.0, read=50.0, write=25.0, pool=6.0),
                httpx.Timeout(connect=6.0, read=65.0, write=25.0, pool=6.0),
            ]
        elif is_setup_contract:
            attempt_timeouts = [
                httpx.Timeout(connect=4.0, read=45.0, write=20.0, pool=4.0),
                httpx.Timeout(connect=5.0, read=85.0, write=25.0, pool=5.0),
            ]
        elif is_setup_analysis:
            attempt_timeouts = [
                httpx.Timeout(connect=3.0, read=14.0, write=12.0, pool=3.0),
                httpx.Timeout(connect=4.0, read=20.0, write=14.0, pool=4.0),
            ]
        else:
            # Keep standard chat responsive.
            attempts = max(1, self.chat_retry_attempts)
            attempt_timeouts = []
            for attempt_idx in range(attempts):
                growth = 1.0 + (0.25 * attempt_idx)
                attempt_timeouts.append(
                    httpx.Timeout(
                        connect=max(1.0, self.chat_timeout_connect + (0.5 * attempt_idx)),
                        read=max(3.0, self.chat_timeout_read * growth),
                        write=max(1.0, self.chat_timeout_write * growth),
                        pool=max(1.0, self.chat_timeout_pool + (0.5 * attempt_idx)),
                    )
                )

        provider_ctx = {
            "session_id": context.session_id,
            "model": chat_model,
            "api_url": api_url,
            "has_image_payload": has_image_payload,
            "setup_contract": is_setup_contract,
            "setup_analysis": is_setup_analysis,
            "attachments": len(attachments or []),
            "max_tokens": max_tokens,
            "language": context.language,
        }
        retryable_statuses = {408, 409, 421, 425, 429, 500, 502, 503, 504}
        try:
            candidates = self._candidate_llm_urls(
                api_url,
                strict_explicit_endpoint=self.strict_explicit_endpoint,
            )
            last_error = "unknown"
            attempted: list[str] = []
            for target_url, kind in candidates:
                max_attempts = len(attempt_timeouts)
                for attempt in range(1, max_attempts + 1):
                    attempted.append(f"{target_url} ({kind})")
                    request_payload = dict(responses_payload if kind == "responses" else payload)
                    token_key = "max_output_tokens" if kind == "responses" else "max_tokens"
                    if attempt >= 2 and token_key in request_payload:
                        request_payload[token_key] = max(128, int(request_payload[token_key] * 0.6))
                    timeout = attempt_timeouts[min(attempt - 1, len(attempt_timeouts) - 1)]
                    logger.debug(
                        "LLM provider attempt start (attempt=%s/%s, kind=%s, url=%s, timeout_connect=%s, timeout_read=%s, timeout_write=%s, timeout_pool=%s, token_budget=%s, session=%s, model=%s)",
                        attempt,
                        max_attempts,
                        kind,
                        target_url,
                        timeout.connect,
                        timeout.read,
                        timeout.write,
                        timeout.pool,
                        request_payload.get(token_key),
                        context.session_id,
                        chat_model,
                    )
                    try:
                        started = time.perf_counter()
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
                            elapsed_ms = int((time.perf_counter() - started) * 1000)
                            logger.info(
                                "LLM provider call succeeded (attempt=%s, kind=%s, url=%s, elapsed_ms=%s, session=%s, model=%s)",
                                attempt,
                                kind,
                                target_url,
                                elapsed_ms,
                                context.session_id,
                                chat_model,
                            )
                            return text
                        last_error = f"empty response from {target_url}"
                        if attempt < max_attempts:
                            delay = self._retry_delay_seconds(attempt)
                            time.sleep(delay)
                    except httpx.TimeoutException:
                        last_error = f"timeout at {target_url}"
                        logger.warning(
                            "LLM provider timeout (attempt=%s, kind=%s, url=%s, session=%s, model=%s, has_image=%s)",
                            attempt,
                            kind,
                            target_url,
                            context.session_id,
                            chat_model,
                            has_image_payload,
                        )
                        logger.debug(
                            "LLM provider timeout details (attempt=%s/%s, kind=%s, url=%s, timeout_connect=%s, timeout_read=%s, timeout_write=%s, timeout_pool=%s, session=%s)",
                            attempt,
                            max_attempts,
                            kind,
                            target_url,
                            timeout.connect,
                            timeout.read,
                            timeout.write,
                            timeout.pool,
                            context.session_id,
                        )
                        if attempt < max_attempts:
                            delay = self._retry_delay_seconds(attempt)
                            logger.debug(
                                "LLM provider retry scheduled after timeout (attempt=%s, delay_seconds=%.2f, url=%s, session=%s)",
                                attempt,
                                delay,
                                target_url,
                                context.session_id,
                            )
                            time.sleep(delay)
                            continue
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code if exc.response is not None else "unknown"
                        body = (exc.response.text[:220] if exc.response is not None else "").strip()
                        request_id = ""
                        retry_after = ""
                        if exc.response is not None:
                            request_id = (
                                exc.response.headers.get("x-request-id")
                                or exc.response.headers.get("request-id")
                                or ""
                            )
                            retry_after = (
                                exc.response.headers.get("retry-after")
                                or exc.response.headers.get("x-ratelimit-reset")
                                or ""
                            )
                        last_error = f"http {status} at {target_url}{(': ' + body) if body else ''}"
                        logger.warning(
                            "LLM provider HTTP error (attempt=%s, kind=%s, status=%s, url=%s, request_id=%s, retry_after=%s, body=%s, session=%s, model=%s)",
                            attempt,
                            kind,
                            status,
                            target_url,
                            request_id or "-",
                            retry_after or "-",
                            body or "-",
                            context.session_id,
                            chat_model,
                        )
                        if status in (400, 401, 402, 403, 422):
                            raise RuntimeError(last_error)
                        if status in retryable_statuses and attempt < max_attempts:
                            delay = self._retry_delay_seconds(attempt, retry_after)
                            time.sleep(delay)
                            continue
                        break
                    except Exception as exc:
                        last_error = f"{exc.__class__.__name__} at {target_url}"
                        logger.exception(
                            "LLM provider unexpected error (attempt=%s, kind=%s, url=%s, session=%s, model=%s)",
                            attempt,
                            kind,
                            target_url,
                            context.session_id,
                            chat_model,
                        )
                        if attempt < max_attempts:
                            delay = self._retry_delay_seconds(attempt)
                            time.sleep(delay)
                            continue
                        break
            attempted_hint = ", ".join(dict.fromkeys(attempted))
            logger.error(
                "LLM provider attempts exhausted (last_error=%s, tried=%s, context=%s)",
                last_error,
                attempted_hint,
                provider_ctx,
            )
            raise RuntimeError(f"{last_error}; tried={attempted_hint}")
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            logger.warning(
                "LLM provider rejected request (status=%s, context=%s)",
                status,
                provider_ctx,
            )
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
            err_text = str(exc)
            lower_err = err_text.lower()
            logger.error(
                "LLM provider runtime failure: %s | context=%s",
                err_text,
                provider_ctx,
            )
            is_timeout_like = (
                ("timeout" in lower_err)
                or ("timed out" in lower_err)
                or ("attempts exhausted" in lower_err)
                or ("provider timeout" in lower_err)
            )
            if is_timeout_like:
                if context.language == "en":
                    return (
                        "The provider is currently slow/unreachable. "
                        "Please retry in a moment."
                    )
                return (
                    "Der Provider ist aktuell langsam/nicht erreichbar. "
                    "Bitte versuche es gleich erneut."
                )
            if context.language == "en":
                return (
                    f"Provider request failed ({err_text}). "
                    "Please verify endpoint/model/API key compatibility."
                )
            return (
                f"Provider-Anfrage fehlgeschlagen ({err_text}). "
                "Bitte Endpoint/Modell/API-Key-Kompatibilitaet pruefen."
            )
        except Exception:
            logger.exception("LLM provider request failed unexpectedly. context=%s", provider_ctx)
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
