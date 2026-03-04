from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api.runtime import (
    find_or_create_draft_setup_session,
    get_db_session,
    hash_password,
    mint_auth_token,
    normalize_email,
    persist_auth_token,
    resolve_user_id_from_token,
    verify_password,
)
from chastease.compat.rate_limit import Limiter, get_remote_address
from chastease.api.schemas import LoginRequest, RegisterRequest
from chastease.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register")
@limiter.limit("10/minute")
def register(payload: RegisterRequest, request: Request) -> dict:
    db = get_db_session(request)
    try:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        email = normalize_email(payload.email)
        display_name = username
        existing_email = db.scalar(select(User).where(User.email == email))
        if existing_email is not None:
            raise HTTPException(status_code=409, detail="Email already registered.")
        existing_username = db.scalar(select(User).where(func.lower(User.display_name) == username.lower()))
        if existing_username is not None:
            raise HTTPException(status_code=409, detail="Username already registered.")

        user = User(
            id=str(uuid4()),
            email=email,
            display_name=display_name,
            password_hash=hash_password(payload.password),
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()

        ttl_days = int(getattr(request.app.state.config, "AUTH_TOKEN_TTL_DAYS", 30))
        token = mint_auth_token(user.id, request.app.state.config.SECRET_KEY)
        persist_auth_token(token, user.id, db, ttl_days)
        draft_id, draft_session = find_or_create_draft_setup_session(user.id, "de")
        return {
            "user_id": user.id,
            "username": username,
            "email": user.email,
            "display_name": user.display_name,
            "auth_token": token,
            "setup_session_id": draft_id,
            "setup_status": draft_session["status"],
        }
    finally:
        db.close()


@router.post("/login")
@limiter.limit("20/minute")
def login(payload: LoginRequest, request: Request) -> dict:
    db = get_db_session(request)
    try:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        user = db.scalar(select(User).where(func.lower(User.display_name) == username.lower()))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        ttl_days = int(getattr(request.app.state.config, "AUTH_TOKEN_TTL_DAYS", 30))
        token = mint_auth_token(user.id, request.app.state.config.SECRET_KEY)
        persist_auth_token(token, user.id, db, ttl_days)
        draft_id, draft_session = find_or_create_draft_setup_session(user.id, "de")
        return {
            "user_id": user.id,
            "username": user.display_name,
            "email": user.email,
            "display_name": user.display_name,
            "auth_token": token,
            "setup_session_id": draft_id,
            "setup_status": draft_session["status"],
        }
    finally:
        db.close()


@router.get("/me")
def auth_me(auth_token: str, request: Request) -> dict:
    user_id = resolve_user_id_from_token(auth_token, request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token.")

    db = get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid auth token.")
        return {"user_id": user.id, "email": user.email, "display_name": user.display_name}
    finally:
        db.close()
