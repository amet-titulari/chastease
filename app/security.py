from fastapi import Header, HTTPException

from app.config import settings


def verify_admin_secret(x_admin_secret: str | None = Header(default=None)) -> None:
    expected = settings.admin_secret
    if not expected:
        return
    if x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
