from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _normalize_sqlite_url(url: str) -> str:
    if not isinstance(url, str):
        return url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url

    raw_path = url[len(prefix):]
    if raw_path.startswith("/"):
        return url

    absolute_path = (PROJECT_ROOT / raw_path).resolve()
    return f"{prefix}{absolute_path.as_posix()}"


def _normalize_local_path(path_value: str) -> str:
    if not isinstance(path_value, str):
        return path_value
    path = Path(path_value)
    if path.is_absolute():
        return path_value
    return str((PROJECT_ROOT / path).resolve())


class Settings(BaseSettings):
    app_name: str = "Chastease"
    debug: bool = False
    cookie_secure: bool = False
    database_url: str = "sqlite:///./data/chastease.db"
    media_dir: str = "./data/media"
    allow_insecure_dev_mode: bool = False
    hygiene_overdue_penalty_seconds: int = 600
    hygiene_opening_max_duration_seconds: int = 900
    local_timezone: str = "Europe/Berlin"
    task_overdue_default_penalty_seconds: int = 300
    task_overdue_sweeper_enabled: bool = True
    task_overdue_sweeper_interval_seconds: int = 60
    proactive_messages_enabled: bool = True
    proactive_messages_interval_seconds: int = 120
    proactive_messages_cooldown_seconds: int = 600
    proactive_messages_max_consecutive: int = 3
    session_timer_sweeper_enabled: bool = True
    session_timer_sweeper_interval_seconds: int = 30
    admin_secret: str | None = None
    secret_encryption_key: str | None = None
    admin_bootstrap_emails: str = ""
    ai_provider: str = "stub"
    ai_api_url: str | None = None
    ai_api_key: str | None = None
    ai_chat_model: str | None = None
    ai_vision_model: str | None = None
    ai_ollama_base_url: str = "http://127.0.0.1:11434"
    ai_ollama_model: str = "llama3.1"
    ai_ollama_timeout_seconds: float = 15.0
    web_push_enabled: bool = False
    web_push_vapid_public_key: str | None = None
    web_push_vapid_private_key: str | None = None
    web_push_vapid_claims_sub: str = "mailto:admin@localhost"
    verification_ai_provider: str = "auto"
    verification_ollama_model: str = "llava"
    verification_ollama_timeout_seconds: float = 20.0
    transcription_enabled: bool = True
    transcription_provider: str = "auto"
    transcription_api_url: str | None = None
    transcription_api_key: str | None = None
    transcription_model: str = "whisper-1"
    transcription_language: str | None = "de"
    transcription_timeout_seconds: float = 45.0
    voice_realtime_enabled: bool = False
    voice_realtime_ws_url: str = "wss://api.x.ai/v1/realtime"
    voice_realtime_client_secret_url: str = "https://api.x.ai/v1/realtime/client_secrets"
    voice_realtime_api_key: str | None = None
    voice_realtime_mode: str = "realtime-manual"
    voice_realtime_agent_id: str | None = None
    voice_realtime_default_voice: str = "Eve"
    voice_realtime_expires_seconds: int = 300
    lovense_enabled: bool = False
    lovense_platform: str | None = None
    lovense_developer_token: str | None = None
    lovense_app_type: str = "connect"
    lovense_sdk_url: str = "https://api.lovense-api.com/basic-sdk/core.min.js"
    lovense_api_base_url: str = "https://api.lovense-api.com/api/basicApi"
    lovense_debug: bool = False
    lovense_simulator_enabled: bool = False
    verification_media_retention_enabled: bool = True
    verification_media_retention_hours: int = 72
    # Audit log – set CHASTEASE_AUDIT_LOG_ENABLED=true to activate
    audit_log_enabled: bool = False
    audit_log_path: str = "./data/audit.log"
    # WebSocket debug output panel in play view
    play_ws_debug_enabled: bool = False

    model_config = SettingsConfigDict(
        env_prefix="CHASTEASE_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
settings.database_url = _normalize_sqlite_url(settings.database_url)
settings.media_dir = _normalize_local_path(settings.media_dir)
