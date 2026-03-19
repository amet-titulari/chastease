import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from app.config import settings


_ENCRYPTED_PREFIX = "enc::"
_FERNET: Fernet | None = None


def _build_fernet() -> Fernet:
    global _FERNET
    if _FERNET is not None:
        return _FERNET

    source = settings.secret_encryption_key or settings.admin_secret or settings.app_name
    key = base64.urlsafe_b64encode(hashlib.sha256(str(source).encode("utf-8")).digest())
    _FERNET = Fernet(key)
    return _FERNET


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return text
    if text.startswith(_ENCRYPTED_PREFIX):
        return text
    token = _build_fernet().encrypt(text.encode("utf-8")).decode("utf-8")
    return f"{_ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text.startswith(_ENCRYPTED_PREFIX):
        return text
    token = text[len(_ENCRYPTED_PREFIX):]
    try:
        return _build_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        _ = dialect
        return encrypt_secret(value)

    def process_result_value(self, value, dialect):
        _ = dialect
        return decrypt_secret(value)
