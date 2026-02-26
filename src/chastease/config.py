import os
import secrets
from pathlib import Path


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


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def _resolve_secret_key() -> str:
    configured = os.getenv("SECRET_KEY")
    if configured is not None and configured.strip():
        return configured.strip()

    key_file = os.getenv("SECRET_KEY_FILE", "data/secret_key.txt").strip() or "data/secret_key.txt"
    key_path = Path(key_file)
    if not key_path.is_absolute():
        key_path = Path.cwd() / key_path

    try:
        if key_path.exists():
            existing = key_path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        key_path.parent.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_urlsafe(48)
        key_path.write_text(generated, encoding="utf-8")
        return generated
    except Exception:
        return "dev-secret-change-me"


class Config:
    def __init__(self) -> None:
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        self.SECRET_KEY = _resolve_secret_key()
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/chastease.db")
        self.ENABLE_SESSION_KILL = _env_bool("ENABLE_SESSION_KILL", False)
        self.AUTH_TOKEN_TTL_DAYS = max(1, _env_int("AUTH_TOKEN_TTL_DAYS", 30))
        self.IMAGE_VERIFICATION_DIR = os.getenv("IMAGE_VERIFICATION_DIR", "data/image_verifications")
        self.TTL_API_BASE = os.getenv("TTL_API_BASE", "https://euapi.ttlock.com")
        self.TTL_CLIENT_ID = os.getenv("TTL_CLIENT_ID", "")
        self.TTL_CLIENT_SECRET = os.getenv("TTL_CLIENT_SECRET", "")
        self.LLM_STRICT_EXPLICIT_ENDPOINT = _env_bool("LLM_STRICT_EXPLICIT_ENDPOINT", True)
        self.LLM_CHAT_HISTORY_TURNS = max(1, _env_int("LLM_CHAT_HISTORY_TURNS", 3))
        self.LLM_CHAT_HISTORY_CHARS_PER_TURN = max(80, _env_int("LLM_CHAT_HISTORY_CHARS_PER_TURN", 280))
        self.LLM_CHAT_INCLUDE_TOOLS_SUMMARY = _env_bool("LLM_CHAT_INCLUDE_TOOLS_SUMMARY", False)
        self.LLM_CHAT_MAX_TOKENS = max(64, _env_int("LLM_CHAT_MAX_TOKENS", 220))
        self.LLM_CHAT_RETRY_ATTEMPTS = max(1, _env_int("LLM_CHAT_RETRY_ATTEMPTS", 1))
        self.LLM_CHAT_TIMEOUT_CONNECT = max(1.0, _env_float("LLM_CHAT_TIMEOUT_CONNECT", 3.0))
        self.LLM_CHAT_TIMEOUT_READ = max(3.0, _env_float("LLM_CHAT_TIMEOUT_READ", 10.0))
        self.LLM_CHAT_TIMEOUT_WRITE = max(1.0, _env_float("LLM_CHAT_TIMEOUT_WRITE", 10.0))
        self.LLM_CHAT_TIMEOUT_POOL = max(1.0, _env_float("LLM_CHAT_TIMEOUT_POOL", 3.0))
        self.LLM_FAIL_CLOSED_REQUEST_TAG = _env_bool("LLM_FAIL_CLOSED_REQUEST_TAG", True)
        self.ENABLE_AUDIT_LOG_VIEW = _env_bool("ENABLE_AUDIT_LOG_VIEW", False)
        self.AI_SESSION_READ_TOKEN = os.getenv("AI_SESSION_READ_TOKEN", "").strip()
