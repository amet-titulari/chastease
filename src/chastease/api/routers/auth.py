from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api import routes as legacy
from chastease.api.schemas import LoginRequest, RegisterRequest
from chastease.models import User
from chastease.repositories.setup_store import load_sessions, save_sessions

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, request: Request) -> dict:
    db = legacy._get_db_session(request)
    try:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        email = legacy._normalize_email(payload.email)
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
            password_hash=legacy._hash_password(payload.password),
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()

        token = legacy._mint_auth_token(user.id, request.app.state.config.SECRET_KEY)
        legacy.auth_tokens[token] = user.id
        store = load_sessions()
        draft_id, draft_session = legacy._find_user_setup_session(store, user.id, {"draft", "setup_in_progress"})
        if draft_session is None:
            draft_session = legacy._create_draft_setup_session(user.id, "de")
            draft_id = draft_session["setup_session_id"]
            store[draft_id] = draft_session
            save_sessions(store)
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
def login(payload: LoginRequest, request: Request) -> dict:
    db = legacy._get_db_session(request)
    try:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        user = db.scalar(select(User).where(func.lower(User.display_name) == username.lower()))
        if user is None or not legacy._verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        token = legacy._mint_auth_token(user.id, request.app.state.config.SECRET_KEY)
        legacy.auth_tokens[token] = user.id
        store = load_sessions()
        draft_id, draft_session = legacy._find_user_setup_session(store, user.id, {"draft", "setup_in_progress"})
        if draft_session is None:
            draft_session = legacy._create_draft_setup_session(user.id, "de")
            draft_id = draft_session["setup_session_id"]
            store[draft_id] = draft_session
            save_sessions(store)
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
    user_id = legacy._resolve_user_id_from_token(auth_token, request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token.")

    db = legacy._get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid auth token.")
        return {"user_id": user.id, "email": user.email, "display_name": user.display_name}
    finally:
        db.close()
