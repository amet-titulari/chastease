from typing import Any, Literal

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
    action_id: str | None = Field(default=None, min_length=8)


class ChatActionResolveRequest(BaseModel):
    session_id: str = Field(min_length=1)
    action_id: str = Field(min_length=8)
    resolution_status: Literal["success", "failed"]
    expected_status: Literal["pending"] = "pending"
    note: str = Field(default="", max_length=500)


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
    roleplay_character_id: str | None = None
    roleplay_scenario_id: str | None = None
    auth_token: str = Field(min_length=8)
    hard_stop_enabled: bool = True
    autonomy_mode: Literal["execute", "suggest"] = "execute"
    integrations: list[Literal["ttlock", "chaster", "emlalock"]] = Field(default_factory=list)
    integration_config: dict[str, dict[str, Any]] = Field(default_factory=dict)
    language: Literal["de", "en"] = "de"
    blocked_trigger_words: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    contract_start_date: str | None = None
    contract_end_date: str | None = None  # legacy fixed end date
    contract_min_end_date: str | None = None
    contract_max_end_date: str | None = None
    ai_controls_end_date: bool = True
    max_penalty_per_day_minutes: int = Field(default=0, ge=0, le=1440)
    max_penalty_per_week_minutes: int = Field(default=0, ge=0, le=10080)
    opening_limit_period: Literal["day", "week", "month"] = "month"
    max_openings_in_period: int = Field(default=7, ge=0, le=200)
    max_openings_per_day: int | None = Field(default=None, ge=0, le=10)  # legacy alias
    opening_window_minutes: int = Field(default=15, ge=1, le=240)
    seal_mode: Literal["none", "plomben", "versiegelung"] = "none"
    initial_seal_number: str | None = Field(default=None, min_length=3)
    instruction_style: Literal["direct_command", "polite_authoritative", "suggestive", "mixed"] = "mixed"
    desired_intensity: Literal["low", "medium", "strong", "demanding"] = "strong"
    grooming_preference: Literal["no_preference", "clean_shaven", "trimmed", "natural"] = "clean_shaven"


class SetupAnswer(BaseModel):
    question_id: str
    value: int | str


class SetupAnswersRequest(BaseModel):
    answers: list[SetupAnswer]


class SetupAICalibrationTurnRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    wearer_message: str | None = None


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
    integration_config: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SetupSealUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    seal_mode: Literal["none", "plomben", "versiegelung"] = "none"


class SetupRoleplaySelectionRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    roleplay_character_id: str | None = None
    roleplay_scenario_id: str | None = None
    prompt_profile_name: str | None = Field(default=None, max_length=80)
    prompt_profile_mode: str | None = Field(default=None, max_length=80)
    prompt_profile_version: str | None = Field(default=None, max_length=40)


class RoleplayCharacterUpsertRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=120)
    persona_name: str | None = Field(default=None, max_length=120)
    archetype: str = Field(default="keyholder", min_length=2, max_length=80)
    description: str = Field(default="", max_length=2000)
    greeting_template: str = Field(default="", max_length=1000)
    tone: str = Field(default="balanced", min_length=2, max_length=80)
    dominance_style: str = Field(default="moderate", min_length=2, max_length=80)
    ritual_phrases: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    scenario_hooks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class RoleplayScenarioUpsertRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=2000)
    phase_id: str = Field(default="active", min_length=1, max_length=80)
    phase_title: str = Field(default="Active Session", min_length=1, max_length=120)
    phase_objective: str = Field(default="", max_length=1000)
    phase_guidance: str = Field(default="", max_length=2000)
    lore_key: str = Field(default="session-rules", min_length=1, max_length=80)
    lore_content: str = Field(default="", max_length=4000)
    lore_triggers: list[str] = Field(default_factory=list)
    lore_priority: int = Field(default=100, ge=0, le=1000)
    tags: list[str] = Field(default_factory=list)


class RoleplayLibraryImportRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    overwrite_existing: bool = False
    library: dict[str, Any] = Field(default_factory=dict)
    characters: list[dict[str, Any]] = Field(default_factory=list)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)

class SetupAIControlledFieldsUpdateRequest(BaseModel):
    """Nur KI darf diese geschützten Felder aktualisieren."""
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    updates: dict = Field(default_factory=dict)  # z.B. {"contract_min_end_date": "2026-03-15", "opening_limit_period": "day"}
    reason: str = Field(default="", max_length=500)  # Grund für die KI-Anpassung
