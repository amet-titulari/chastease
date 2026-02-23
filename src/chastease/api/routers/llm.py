from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from chastease.api.runtime import get_db_session, require_user_token, serialize_llm_profile
from chastease.api.schemas import LLMProfileTestRequest, LLMProfileUpsertRequest
from chastease.models import LLMProfile
from chastease.services.ai.base import StoryTurnContext
from chastease.shared.secrets_crypto import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/profile")
def get_llm_profile(user_id: str, auth_token: str, request: Request) -> dict:
    db = get_db_session(request)
    try:
        require_user_token(user_id, auth_token, db, request)
        profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == user_id))
        if profile is None:
            return {"configured": False}
        return {"configured": True, "profile": serialize_llm_profile(profile)}
    finally:
        db.close()


@router.post("/profile")
def upsert_llm_profile(payload: LLMProfileUpsertRequest, request: Request) -> dict:
    db = get_db_session(request)
    try:
        require_user_token(payload.user_id, payload.auth_token, db, request)
        profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == payload.user_id))
        now = datetime.now(UTC)
        encrypted_key = (
            encrypt_secret(payload.api_key, request.app.state.config.SECRET_KEY)
            if payload.api_key and payload.api_key.strip()
            else None
        )

        if profile is None:
            if not encrypted_key:
                raise HTTPException(status_code=400, detail="api_key is required for first profile creation.")
            profile = LLMProfile(
                id=str(uuid4()),
                user_id=payload.user_id,
                provider_name=payload.provider_name.strip(),
                api_url=payload.api_url.strip(),
                api_key_encrypted=encrypted_key,
                chat_model=payload.chat_model.strip(),
                vision_model=(payload.vision_model.strip() if payload.vision_model else None),
                behavior_prompt=payload.behavior_prompt,
                is_active=payload.is_active,
                created_at=now,
                updated_at=now,
            )
            db.add(profile)
        else:
            profile.provider_name = payload.provider_name.strip()
            profile.api_url = payload.api_url.strip()
            if encrypted_key:
                profile.api_key_encrypted = encrypted_key
            profile.chat_model = payload.chat_model.strip()
            profile.vision_model = payload.vision_model.strip() if payload.vision_model else None
            profile.behavior_prompt = payload.behavior_prompt
            profile.is_active = payload.is_active
            profile.updated_at = now
            db.add(profile)
        db.commit()
        return {"configured": True, "profile": serialize_llm_profile(profile)}
    finally:
        db.close()


@router.post("/test")
def test_llm_profile(payload: LLMProfileTestRequest, request: Request) -> dict:
    db = get_db_session(request)
    try:
        require_user_token(payload.user_id, payload.auth_token, db, request)
        profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == payload.user_id))

        provider_name = (
            str(payload.provider_name).strip()
            if payload.provider_name is not None
            else (str(profile.provider_name).strip() if profile is not None else "custom")
        )
        api_url = (
            str(payload.api_url).strip()
            if payload.api_url is not None
            else (str(profile.api_url).strip() if profile is not None else "")
        )
        chat_model = (
            str(payload.chat_model).strip()
            if payload.chat_model is not None
            else (str(profile.chat_model).strip() if profile is not None else "")
        )
        vision_model = (
            str(payload.vision_model).strip()
            if payload.vision_model is not None
            else (str(profile.vision_model).strip() if (profile is not None and profile.vision_model) else "")
        )
        behavior_prompt = (
            str(payload.behavior_prompt)
            if payload.behavior_prompt is not None
            else (str(profile.behavior_prompt or "") if profile is not None else "")
        )
        is_active = payload.is_active if payload.is_active is not None else (bool(profile.is_active) if profile is not None else True)
        provided_api_key = str(payload.api_key or "").strip()

        if profile is None and not (api_url and chat_model):
            raise HTTPException(status_code=404, detail="LLM profile not configured.")
        if not is_active:
            raise HTTPException(status_code=400, detail="LLM profile is disabled.")

        if payload.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "profile": {
                    "provider_name": provider_name,
                    "api_url": api_url,
                    "chat_model": chat_model,
                    "vision_model": (vision_model or None),
                    "has_api_key": bool(provided_api_key or (profile.api_key_encrypted if profile is not None else "")),
                },
            }

        if not api_url:
            raise HTTPException(status_code=400, detail="api_url is required for live test.")
        if not chat_model:
            raise HTTPException(status_code=400, detail="chat_model is required for live test.")

        if provided_api_key:
            api_key = provided_api_key
        else:
            if profile is None or not profile.api_key_encrypted:
                raise HTTPException(status_code=400, detail="api_key is required for live test.")
            try:
                api_key = decrypt_secret(profile.api_key_encrypted, request.app.state.config.SECRET_KEY)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Stored API key cannot be decrypted with current SECRET_KEY. "
                        "Please save the LLM profile again with a fresh API key."
                    ),
                ) from exc
        ai_service = request.app.state.ai_service
        context = StoryTurnContext(
            session_id="llm-connectivity-test",
            action="Ping test action",
            language="en",
            psychogram_summary="test profile",
        )
        if hasattr(ai_service, "generate_narration_with_profile"):
            narration = ai_service.generate_narration_with_profile(
                context,
                api_url=api_url,
                api_key=api_key,
                chat_model=chat_model,
                behavior_prompt=behavior_prompt,
            )
        else:
            narration = ai_service.generate_narration(context)

        return {"ok": True, "dry_run": False, "sample_response": narration}
    finally:
        db.close()
