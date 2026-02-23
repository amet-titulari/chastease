import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/chastease.db")
        self.ENABLE_SESSION_KILL = _env_bool("ENABLE_SESSION_KILL", False)
        self.AUTH_TOKEN_TTL_DAYS = max(1, _env_int("AUTH_TOKEN_TTL_DAYS", 30))
        self.IMAGE_VERIFICATION_DIR = os.getenv("IMAGE_VERIFICATION_DIR", "data/image_verifications")
