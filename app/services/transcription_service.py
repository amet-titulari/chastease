from dataclasses import dataclass
import os

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.llm_profile import LlmProfile
from app.models.session import Session as SessionModel


@dataclass
class TranscriptionResult:
    status: str
    text: str | None = None
    provider: str | None = None
    model: str | None = None
    error: str | None = None


def _derive_transcription_url(chat_api_url: str | None) -> str | None:
    if not chat_api_url:
        return None
    url = chat_api_url.strip()
    if not url:
        return None
    if "/chat/completions" in url:
        return url.replace("/chat/completions", "/audio/transcriptions")
    if url.endswith("/responses"):
        return url[: -len("/responses")] + "/audio/transcriptions"
    if url.endswith("/"):
        return f"{url}audio/transcriptions"
    return f"{url}/audio/transcriptions"


def _resolve_transcription_target(db: Session, session_obj: SessionModel | None) -> tuple[str | None, str | None]:
    if settings.transcription_api_url and settings.transcription_api_key:
        return settings.transcription_api_url, settings.transcription_api_key

    if session_obj is not None and session_obj.llm_api_url and session_obj.llm_api_key:
        return _derive_transcription_url(session_obj.llm_api_url), session_obj.llm_api_key

    llm_default = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if llm_default and llm_default.api_url and llm_default.api_key:
        return _derive_transcription_url(llm_default.api_url), llm_default.api_key

    env_key = os.getenv("XAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if env_key:
        return _derive_transcription_url("https://api.x.ai/v1/chat/completions"), env_key

    if settings.transcription_api_url:
        return settings.transcription_api_url, settings.transcription_api_key

    return None, None


def transcribe_audio(
    db: Session,
    audio_bytes: bytes,
    filename: str,
    mime_type: str,
    session_obj: SessionModel | None,
) -> TranscriptionResult:
    if not settings.transcription_enabled:
        return TranscriptionResult(status="disabled")

    provider = settings.transcription_provider.strip().lower() if settings.transcription_provider else "auto"
    if provider not in {"auto", "openai-compatible", "xai", "openai"}:
        return TranscriptionResult(status="unsupported-provider", error=f"Unsupported provider: {provider}")

    api_url, api_key = _resolve_transcription_target(db=db, session_obj=session_obj)
    if not api_url or not api_key:
        return TranscriptionResult(status="unavailable", error="No transcription API credentials configured")

    model = settings.transcription_model.strip() or "whisper-1"
    form_data = {"model": model}
    if settings.transcription_language:
        form_data["language"] = settings.transcription_language

    try:
        with httpx.Client(timeout=settings.transcription_timeout_seconds) as client:
            resp = client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                data=form_data,
                files={"file": (filename or "audio.webm", audio_bytes, mime_type or "application/octet-stream")},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        return TranscriptionResult(status="error", error=str(exc)[:300], provider=provider, model=model)

    text = payload.get("text") if isinstance(payload, dict) else None
    if not text and isinstance(payload, dict):
        # Some providers return nested structures.
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                text = first.get("text") or first.get("transcript")

    if not text or not str(text).strip():
        return TranscriptionResult(status="empty", error="Transcription returned no text", provider=provider, model=model)

    return TranscriptionResult(
        status="ok",
        text=str(text).strip(),
        provider=provider,
        model=model,
    )
