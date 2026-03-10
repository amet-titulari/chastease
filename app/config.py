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

    model_config = SettingsConfigDict(
        env_prefix="CHASTEASE_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
