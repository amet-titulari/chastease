import base64
import hashlib
import hmac
import secrets


def _derive_keystream(secret_key: str, salt: bytes, length: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret_key.encode("utf-8"),
        salt,
        120_000,
        dklen=length,
    )


def encrypt_secret(plaintext: str, secret_key: str) -> str:
    plain = plaintext.encode("utf-8")
    salt = secrets.token_bytes(16)
    keystream = _derive_keystream(secret_key, salt, len(plain))
    cipher = bytes([p ^ k for p, k in zip(plain, keystream)])
    tag = hmac.new(secret_key.encode("utf-8"), salt + cipher, hashlib.sha256).digest()
    token = salt + tag + cipher
    return base64.urlsafe_b64encode(token).decode("ascii")


def decrypt_secret(token: str, secret_key: str) -> str:
    raw = base64.urlsafe_b64decode(token.encode("ascii"))
    if len(raw) < 48:
        raise ValueError("Invalid encrypted secret format.")
    salt = raw[:16]
    expected_tag = raw[16:48]
    cipher = raw[48:]
    actual_tag = hmac.new(secret_key.encode("utf-8"), salt + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_tag, actual_tag):
        raise ValueError("Encrypted secret integrity check failed.")
    keystream = _derive_keystream(secret_key, salt, len(cipher))
    plain = bytes([c ^ k for c, k in zip(cipher, keystream)])
    return plain.decode("utf-8")
