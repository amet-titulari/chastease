from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chastease"
    debug: bool = True
    database_url: str = "sqlite:///./data/chastease.db"
    media_dir: str = "./data/media"
    hygiene_overdue_penalty_seconds: int = 600
    task_overdue_default_penalty_seconds: int = 300
    task_overdue_sweeper_enabled: bool = True
    task_overdue_sweeper_interval_seconds: int = 60
    proactive_messages_enabled: bool = True
    proactive_messages_interval_seconds: int = 120
    proactive_messages_cooldown_seconds: int = 600
    session_timer_sweeper_enabled: bool = True
    session_timer_sweeper_interval_seconds: int = 30
    admin_secret: str | None = None
    ai_provider: str = "stub"
    ai_ollama_base_url: str = "http://127.0.0.1:11434"
    ai_ollama_model: str = "llama3.1"
    ai_ollama_timeout_seconds: float = 15.0
    web_push_enabled: bool = False
    web_push_vapid_public_key: str | None = None
    web_push_vapid_private_key: str | None = None
    web_push_vapid_claims_sub: str = "mailto:admin@localhost"

    model_config = SettingsConfigDict(
        env_prefix="CHASTEASE_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
