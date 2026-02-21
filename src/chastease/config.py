import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/chastease.db")
        self.ENABLE_SESSION_KILL = _env_bool("ENABLE_SESSION_KILL", False)
