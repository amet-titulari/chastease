import hashlib

from pwdlib import PasswordHash


_PASSWORD_HASHER = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _PASSWORD_HASHER.verify(password, password_hash)


def verify_password_and_update(password: str, password_hash: str) -> tuple[bool, str | None]:
    return _PASSWORD_HASHER.verify_and_update(password, password_hash)


def legacy_hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def is_legacy_password_hash(password_hash: str | None) -> bool:
    value = str(password_hash or "")
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def verify_legacy_password(password: str, password_hash: str, salt: str | None) -> bool:
    return legacy_hash_password(password, str(salt or "")) == str(password_hash or "")