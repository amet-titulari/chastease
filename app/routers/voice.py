import base64

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.llm_profile import LlmProfile
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel

router = APIRouter(prefix="/api/voice", tags=["voice"])


def _resolve_xai_key(db: Session, session_obj: SessionModel | None) -> str | None:
    if settings.voice_realtime_api_key:
        return settings.voice_realtime_api_key
    if session_obj is not None and session_obj.llm_api_key:
        return session_obj.llm_api_key
    llm_default = db.query(LlmProfile).filter(LlmProfile.profile_key == "default").first()
    if llm_default and llm_default.api_key:
        return llm_default.api_key
    return None


def _build_realtime_instructions(db: Session, session_obj: SessionModel) -> str:
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    persona_name = persona.name if persona else "Keyholderin"
    player_name = player.nickname if player else "Wearer"

    base = [
        f"Du bist {persona_name}.",
        "Antworte immer auf Deutsch.",
        "Bleibe klar, sicher und respektvoll.",
        f"Du sprichst mit {player_name}.",
    ]
    if persona and persona.system_prompt:
        base.append(persona.system_prompt)
    if persona and persona.speech_style_tone:
        base.append(f"Ton: {persona.speech_style_tone}.")
    if persona and persona.speech_style_dominance:
        base.append(f"Dominanzstil: {persona.speech_style_dominance}.")
    return "\n".join(base)


@router.get("/realtime/{session_id}/status")
def realtime_status(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    key = _resolve_xai_key(db=db, session_obj=session_obj)
    return {
        "session_id": session_id,
        "enabled": bool(settings.voice_realtime_enabled),
        "mode": settings.voice_realtime_mode,
        "has_agent_id": bool(settings.voice_realtime_agent_id),
        "has_api_key": bool(key),
        "ws_url": settings.voice_realtime_ws_url,
    }


@router.post("/realtime/{session_id}/client-secret")
def create_realtime_client_secret(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    if not settings.voice_realtime_enabled:
        raise HTTPException(status_code=409, detail="Realtime voice mode is disabled")

    api_key = _resolve_xai_key(db=db, session_obj=session_obj)
    if not api_key:
        raise HTTPException(status_code=409, detail="No API key available for realtime voice")

    mode = (settings.voice_realtime_mode or "realtime-manual").strip().lower()
    if mode not in {"realtime-manual", "voice-agent"}:
        mode = "realtime-manual"
    if mode == "voice-agent" and not settings.voice_realtime_agent_id:
        raise HTTPException(status_code=409, detail="Voice Agent mode requires a voice agent id")

    expires_seconds = max(30, min(1800, int(settings.voice_realtime_expires_seconds)))
    request_payload = {"expires_after": {"seconds": expires_seconds}}
    if mode == "voice-agent":
        request_payload["voice_agent_id"] = settings.voice_realtime_agent_id

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                settings.voice_realtime_client_secret_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            resp.raise_for_status()
            secret_payload = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to create realtime client secret: {str(exc)[:300]}") from exc

    session_update = {
        "type": "session.update",
        "session": {
            "instructions": _build_realtime_instructions(db=db, session_obj=session_obj),
            "voice": settings.voice_realtime_default_voice,
            "turn_detection": {"type": "server_vad"},
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": 24000}},
                "output": {"format": {"type": "audio/pcm", "rate": 24000}},
            },
        },
    }

    payload = {
        "session_id": session_id,
        "mode": mode,
        "ws_url": settings.voice_realtime_ws_url,
        "client_secret": secret_payload,
        "hints": {
            "requires_subprotocol_prefix": "xai-client-secret.",
            "response_modalities": ["text", "audio"],
        },
    }
    if mode == "realtime-manual":
        payload["session_update"] = session_update
    return payload


@router.post("/tts")
async def tts_proxy(payload: dict) -> dict:
    if not settings.voice_realtime_enabled:
        raise HTTPException(status_code=409, detail="Voice features disabled")
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    voice_id = str(payload.get("voice_id", settings.voice_realtime_default_voice)).strip() or settings.voice_realtime_default_voice

    api_key = settings.voice_realtime_api_key
    if not api_key:
        raise HTTPException(status_code=409, detail="No API key configured for TTS")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.x.ai/v1/tts",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"text": text, "voice_id": voice_id.lower()},
            )
            resp.raise_for_status()
            audio_bytes = resp.content
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TTS request failed: {str(exc)[:300]}") from exc

    return {
        "voice_id": voice_id,
        "mime_type": "audio/mpeg",
        "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
        "size_bytes": len(audio_bytes),
    }
