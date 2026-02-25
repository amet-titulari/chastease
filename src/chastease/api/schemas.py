from typing import Literal

from pydantic import BaseModel, Field


class StoryTurnRequest(BaseModel):
    action: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    session_id: str | None = None


class ChatTurnRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    attachments: list[dict] = Field(default_factory=list)


class SetupChatPreviewRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    message: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    attachments: list[dict] = Field(default_factory=list)


class ChatActionExecuteRequest(BaseModel):
    session_id: str = Field(min_length=1)
    action_type: str = Field(min_length=2)
    payload: dict = Field(default_factory=dict)


class ChatVisionReviewRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    picture_name: str = Field(default="image")
    picture_content_type: str = Field(default="image/jpeg")
    picture_data_url: str = Field(min_length=20)
    verification_instruction: str | None = None
    verification_action_payload: dict = Field(default_factory=dict)
    source: Literal["camera", "upload"] = "upload"


class SetupStartRequest(BaseModel):
    user_id: str = Field(min_length=1)
    character_id: str | None = None
    auth_token: str = Field(min_length=8)
    hard_stop_enabled: bool = True
    autonomy_mode: Literal["execute", "suggest"] = "execute"
    integrations: list[Literal["ttlock", "chaster", "emlalock"]] = Field(default_factory=list)
    integration_config: dict[str, dict[str, str]] = Field(default_factory=dict)
    language: Literal["de", "en"] = "de"
    blocked_trigger_words: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    contract_start_date: str | None = None
    contract_end_date: str | None = None  # legacy fixed end date
    contract_min_end_date: str | None = None
    contract_max_end_date: str | None = None
    ai_controls_end_date: bool = True
    max_penalty_per_day_minutes: int = Field(default=60, ge=0, le=1440)
    max_penalty_per_week_minutes: int = Field(default=240, ge=0, le=10080)
    opening_limit_period: Literal["day", "week", "month"] = "day"
    max_openings_in_period: int = Field(default=1, ge=0, le=200)
    max_openings_per_day: int | None = Field(default=None, ge=0, le=10)  # legacy alias
    opening_window_minutes: int = Field(default=30, ge=1, le=240)


class SetupAnswer(BaseModel):
    question_id: str
    value: int | str


class SetupAnswersRequest(BaseModel):
    answers: list[SetupAnswer]


class PsychogramRecalibrationRequest(BaseModel):
    update_reason: str = Field(min_length=3)
    trait_overrides: dict[str, int] = Field(default_factory=dict)


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    display_name: str = Field(min_length=1)


class CharacterCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    strength: int = Field(default=5, ge=1, le=10)
    intelligence: int = Field(default=5, ge=1, le=10)
    charisma: int = Field(default=5, ge=1, le=10)
    hp: int = Field(default=100, ge=1, le=1000)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3)
    email: str = Field(min_length=5)
    display_name: str | None = None
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)


class LLMProfileUpsertRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    provider_name: str = Field(default="custom", min_length=2)
    api_url: str = Field(min_length=8)
    api_key: str | None = None
    chat_model: str = Field(min_length=2)
    vision_model: str | None = None
    behavior_prompt: str = Field(default="", min_length=0)
    is_active: bool = True


class LLMProfileTestRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    dry_run: bool = True
    provider_name: str | None = None
    api_url: str | None = None
    api_key: str | None = None
    chat_model: str | None = None
    vision_model: str | None = None
    behavior_prompt: str | None = None
    is_active: bool | None = None


class SetupArtifactsRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    force: bool = False


class SetupContractConsentRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    consent_text: str = Field(min_length=3)


class SetupIntegrationsUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    integrations: list[Literal["ttlock", "chaster", "emlalock"]] = Field(default_factory=list)
    integration_config: dict[str, dict[str, str]] = Field(default_factory=dict)
