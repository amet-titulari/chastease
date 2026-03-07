import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import func, select

from chastease.api.questionnaire import SUPPORTED_LANGUAGES, TRANSLATIONS
from chastease.api.setup_domain import _create_draft_setup_session, _find_user_setup_session
from chastease.models import AuthToken, ChastitySession, LLMProfile, User

AUTH_TOKEN_VERSION = "v1"
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

    _argon2 = PasswordHasher()
except Exception:  # pragma: no cover - fallback for restricted/local test environments
    PasswordHasher = None

    class InvalidHashError(Exception):
        pass

    class VerificationError(Exception):
        pass

    class VerifyMismatchError(Exception):
        pass

    _argon2 = None


def lang(value: str) -> str:
    return value if value in SUPPORTED_LANGUAGES else "de"


def t(language: str, key: str) -> str:
    return TRANSLATIONS[lang(language)][key]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def get_db_session(request: Request):
    return request.app.state.db_session_factory()


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def mint_auth_token(user_id: str, secret_key: str) -> str:
    issued_at = int(datetime.now(UTC).timestamp())
    nonce = secrets.token_hex(8)
    payload = f"{AUTH_TOKEN_VERSION}:{user_id}:{issued_at}:{nonce}"
    signature = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{_b64url_encode(payload.encode('utf-8'))}.{_b64url_encode(signature)}"


def _verify_auth_token(token: str, secret_key: str, ttl_days: int) -> str | None:
    if "." not in token:
        return None
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        provided_sig = _b64url_decode(signature_part)
    except Exception:
        return None

    expected_sig = hmac.new(secret_key.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    try:
        payload = payload_bytes.decode("utf-8")
        version, user_id, issued_at_raw, _nonce = payload.split(":", 3)
    except Exception:
        return None
    if version != AUTH_TOKEN_VERSION:
        return None
    try:
        issued_at = int(issued_at_raw)
    except ValueError:
        return None
    ttl_seconds = max(1, ttl_days) * 24 * 60 * 60
    now_ts = int(datetime.now(UTC).timestamp())
    if issued_at > now_ts + 60:
        return None
    if now_ts - issued_at > ttl_seconds:
        return None
    return user_id


def persist_auth_token(token: str, user_id: str, db, ttl_days: int = 30) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
    db_token = AuthToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at,
        revoked=False,
        created_at=datetime.now(UTC),
    )
    db.merge(db_token)
    db.commit()


def resolve_user_id_from_token(auth_token: str, request: Request) -> str | None:
    db = get_db_session(request)
    try:
        db_token = db.get(AuthToken, auth_token)
        if db_token is not None and not db_token.revoked:
            now = datetime.now(UTC)
            expires = db_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if now < expires:
                return db_token.user_id
    except Exception:
        pass
    finally:
        db.close()

    secret_key = request.app.state.config.SECRET_KEY
    ttl_days = int(getattr(request.app.state.config, "AUTH_TOKEN_TTL_DAYS", 30))
    return _verify_auth_token(auth_token, secret_key, ttl_days)


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format.")
    local, domain = email.split("@", 1)
    if not local or "." not in domain:
        raise HTTPException(status_code=400, detail="Invalid email format.")
    return email


def hash_password(password: str) -> str:
    if _argon2 is not None:
        return _argon2.hash(password)
    salt = secrets.token_hex(16)
    encoded = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return f"{salt}${encoded}"


def verify_password(password: str, encoded: str) -> bool:
    if encoded.startswith("$argon2") and _argon2 is not None:
        try:
            return _argon2.verify(encoded, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    if "$" in encoded:
        salt, expected = encoded.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
        return hmac.compare_digest(actual, expected)
    return False


def require_user_token(user_id: str, auth_token: str, db, request: Request) -> User:
    token_user_id = resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def serialize_chastity_session(session: ChastitySession) -> dict:
    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "character_id": session.character_id,
        "status": session.status,
        "language": session.language,
        "policy": json.loads(session.policy_snapshot_json),
        "psychogram": json.loads(session.psychogram_snapshot_json),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


def serialize_llm_profile(profile: LLMProfile) -> dict:
    return {
        "user_id": profile.user_id,
        "provider_name": profile.provider_name,
        "api_url": profile.api_url,
        "chat_model": profile.chat_model,
        "vision_model": profile.vision_model,
        "behavior_prompt": profile.behavior_prompt,
        "is_active": profile.is_active,
        "has_api_key": bool(profile.api_key_encrypted),
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


def find_or_create_draft_setup_session(user_id: str, language: str = "de") -> tuple[str, dict]:
    from chastease.repositories.setup_store import load_sessions, save_sessions

    store = load_sessions()
    draft_id, draft_session = _find_user_setup_session(store, user_id, {"draft", "setup_in_progress"})
    if draft_session is None:
        draft_session = _create_draft_setup_session(user_id, language)
        draft_id = draft_session["setup_session_id"]
        store[draft_id] = draft_session
        save_sessions(store)
    return draft_id, draft_session


def sync_setup_snapshot_to_active_session(request: Request, setup_session: dict) -> bool:
    session_id = setup_session.get("active_session_id")
    if not session_id:
        return False
    db = get_db_session(request)
    try:
        applied = sync_setup_snapshot_to_active_session_db(db, setup_session)
        if not applied:
            return False
        db.commit()
        return True
    finally:
        db.close()


def sync_setup_snapshot_to_active_session_db(db, setup_session: dict) -> bool:
    session_id = setup_session.get("active_session_id")
    if not session_id:
        return False
    db_session = db.get(ChastitySession, session_id)
    if db_session is None:
        return False
    
    # Prepare policy with initial seal number if configured
    policy = setup_session.get("policy_preview") or {}
    if isinstance(policy, dict):
        policy = dict(policy)  # Make a copy
        roleplay_profile = setup_session.get("roleplay_profile")
        if isinstance(roleplay_profile, dict) and roleplay_profile:
            policy["roleplay"] = json.loads(json.dumps(roleplay_profile))
        
        # Initialize runtime_seal with initial seal number if not already present
        if "runtime_seal" not in policy:
            seal_config = policy.get("seal", {})
            seal_mode = seal_config.get("mode", "none")
            initial_seal_number = setup_session.get("initial_seal_number")
            
            if seal_mode in {"plomben", "versiegelung"} and initial_seal_number:
                policy["runtime_seal"] = {
                    "status": "sealed",
                    "current_text": initial_seal_number,
                    "sealed_at": datetime.now(UTC).isoformat(),
                    "needs_new_seal": False
                }
    
    db_session.psychogram_snapshot_json = json.dumps(setup_session["psychogram"])
    db_session.policy_snapshot_json = json.dumps(policy)
    db_session.updated_at = datetime.now(UTC)
    db.add(db_session)
    return True


def find_setup_session_id_for_active_session(user_id: str, active_session_id: str) -> str | None:
    from chastease.repositories.setup_store import load_sessions

    store = load_sessions()
    for candidate_id, candidate in store.items():
        if not isinstance(candidate, dict):
            continue
        if candidate.get("user_id") != user_id:
            continue
        if candidate.get("active_session_id") == active_session_id:
            return candidate_id
    return None
