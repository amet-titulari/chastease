from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.models.auth_user import AuthUser


AUTH_COOKIE_NAME = "chastease_auth"


def verify_admin_secret(x_admin_secret: str | None = Header(default=None)) -> None:
    expected = settings.admin_secret
    if not expected:
        return
    if x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


def require_admin_session_user(request: Request, db: Session) -> AuthUser:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")

    user = db.query(AuthUser).filter(AuthUser.session_token == token).first()
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    if not bool(getattr(user, "is_admin", False)):
        raise HTTPException(status_code=403, detail="admin_required")
    return user
