from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from chastease.api import routes as legacy
from chastease.models import ChastitySession, Turn, User
from chastease.repositories.setup_store import load_sessions, save_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/active")
def get_active_chastity_session(user_id: str, auth_token: str, request: Request) -> dict:
    token_user_id = legacy._resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = legacy._get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        session = db.scalar(
            select(ChastitySession)
            .where(ChastitySession.user_id == user_id)
            .where(ChastitySession.status == "active")
            .order_by(ChastitySession.created_at.desc())
        )
        if session is None:
            return {"has_active_session": False}

        setup_session_id = None
        store = load_sessions()
        for candidate_id, candidate in store.items():
            if not isinstance(candidate, dict):
                continue
            if candidate.get("user_id") != user_id:
                continue
            if candidate.get("active_session_id") == session.id:
                setup_session_id = candidate_id
                break

        return {
            "has_active_session": True,
            "setup_session_id": setup_session_id,
            "chastity_session": legacy._serialize_chastity_session(session),
        }
    finally:
        db.close()


@router.delete("/active")
def kill_active_chastity_session(
    user_id: str, auth_token: str, request: Request, setup_session_id: str | None = None
) -> dict:
    if not getattr(request.app.state.config, "ENABLE_SESSION_KILL", False):
        raise HTTPException(status_code=404, detail="Not found.")

    token_user_id = legacy._resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = legacy._get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        session = db.scalar(
            select(ChastitySession)
            .where(ChastitySession.user_id == user_id)
            .where(ChastitySession.status == "active")
            .order_by(ChastitySession.created_at.desc())
        )
        deleted = False
        killed_session_id = None
        if session is not None:
            turns = db.scalars(select(Turn).where(Turn.session_id == session.id)).all()
            for turn in turns:
                db.delete(turn)
            killed_session_id = session.id
            db.delete(session)
            deleted = True

        db.commit()

        deleted_setup_session = False
        if setup_session_id:
            store = load_sessions()
            setup_session = store.get(setup_session_id)
            if setup_session and setup_session.get("user_id") == user_id:
                del store[setup_session_id]
                save_sessions(store)
                deleted_setup_session = True

        store = load_sessions()
        draft_id, draft_session = legacy._find_user_setup_session(store, user_id, {"draft", "setup_in_progress"})
        if draft_session is None:
            draft_session = legacy._create_draft_setup_session(user_id, "de")
            draft_id = draft_session["setup_session_id"]
            store[draft_id] = draft_session
            save_sessions(store)

        if not deleted and not deleted_setup_session:
            return {
                "deleted": False,
                "reason": "no_active_or_setup_session",
                "setup_session_id": draft_id,
                "setup_status": draft_session["status"],
            }

        return {
            "deleted": deleted or deleted_setup_session,
            "killed_session_id": killed_session_id,
            "deleted_setup_session": deleted_setup_session,
            "setup_session_id": draft_id,
            "setup_status": draft_session["status"],
        }
    finally:
        db.close()


@router.get("/{session_id}")
def get_chastity_session(session_id: str, request: Request) -> dict:
    db = legacy._get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        return legacy._serialize_chastity_session(session)
    finally:
        db.close()


@router.get("/{session_id}/turns")
def get_session_turns(session_id: str, request: Request) -> dict:
    db = legacy._get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        turns = db.scalars(select(Turn).where(Turn.session_id == session_id).order_by(Turn.turn_no)).all()
        return {
            "session_id": session_id,
            "turns": [
                {
                    "turn_no": turn.turn_no,
                    "player_action": turn.player_action,
                    "ai_narration": turn.ai_narration,
                    "language": turn.language,
                    "created_at": legacy._iso_utc(turn.created_at),
                }
                for turn in turns
            ],
        }
    finally:
        db.close()
