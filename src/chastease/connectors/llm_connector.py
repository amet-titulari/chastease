from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select

from chastease.models import LLMProfile
from chastease.services.ai.base import StoryTurnContext
from chastease.shared.secrets_crypto import decrypt_secret


def generate_narration_with_optional_profile(
    db,
    request: Request,
    *,
    user_id: str,
    context: StoryTurnContext,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    ai_service = request.app.state.ai_service
    profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == user_id))

    if profile is not None and profile.is_active and hasattr(ai_service, "generate_narration_with_profile"):
        has_images = any(str(item.get("type", "")).startswith("image/") for item in (attachments or []))
        selected_model = profile.vision_model if has_images and profile.vision_model else profile.chat_model
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
        return ai_service.generate_narration_with_profile(
            context,
            api_url=profile.api_url,
            api_key=api_key,
            chat_model=selected_model,
            behavior_prompt=profile.behavior_prompt,
            attachments=attachments or [],
        )
    return ai_service.generate_narration(context)
