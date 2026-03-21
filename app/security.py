import secrets
from hmac import compare_digest
from urllib.parse import parse_qs, urlsplit

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_user import AuthUser


AUTH_COOKIE_NAME = "chastease_auth"
CSRF_COOKIE_NAME = "chastease_csrf"
SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def is_cookie_secure() -> bool:
    return bool(settings.cookie_secure)


async def extract_csrf_token(request: Request) -> str | None:
    header_token = str(request.headers.get("X-CSRF-Token") or "").strip()
    if header_token:
        return header_token
    content_type = str(request.headers.get("content-type") or "").lower()
    if "application/x-www-form-urlencoded" in content_type:
        try:
            raw_body = await request.body()
        except Exception:
            return None
        form_token = str((parse_qs(raw_body.decode("utf-8", errors="ignore")).get("csrf_token") or [""])[0]).strip()
        if form_token:
            return form_token
    return None


def is_same_origin_request(request: Request) -> bool | None:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin or referer
    if not candidate:
        return None

    parsed = urlsplit(candidate)
    if not parsed.scheme or not parsed.netloc:
        return False

    trusted_origin = f"{request.base_url.scheme}://{request.base_url.netloc}"
    candidate_origin = f"{parsed.scheme}://{parsed.netloc}"
    return compare_digest(candidate_origin, trusted_origin)


def csrf_tokens_match(cookie_token: str | None, request_token: str | None) -> bool:
    if not cookie_token or not request_token:
        return False
    return compare_digest(str(cookie_token), str(request_token))


def verify_admin_secret(x_admin_secret: str | None = Header(default=None)) -> None:
    expected = settings.admin_secret
    if not expected:
        return
    if x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


def require_admin_session_user(request: Request, db: Session = Depends(get_db)) -> AuthUser:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")

    user = db.query(AuthUser).filter(AuthUser.session_token == token).first()
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    if not bool(getattr(user, "is_admin", False)):
        raise HTTPException(status_code=403, detail="admin_required")
    return user
