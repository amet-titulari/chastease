from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from chastease.api.runtime import (
    find_or_create_draft_setup_session,
    find_setup_session_id_for_active_session,
    get_db_session,
    iso_utc,
    resolve_user_id_from_token,
    serialize_chastity_session,
)
from chastease.models import ChastitySession, Turn, User
from chastease.repositories.setup_store import load_sessions, save_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _latest_setup_session_for_user(user_id: str) -> tuple[str, dict] | tuple[None, None]:
    store = load_sessions()
    candidates = []
    for sid, sess in store.items():
        if not isinstance(sess, dict):
            continue
        if sess.get("user_id") != user_id:
            continue
        if sess.get("status") not in {"draft", "setup_in_progress", "configured"}:
            continue
        candidates.append((sid, sess))
    if not candidates:
        return (None, None)
    candidates.sort(key=lambda item: item[1].get("updated_at", item[1].get("created_at", "")), reverse=True)
    return candidates[0]


@router.get("/active")
def get_active_chastity_session(user_id: str, auth_token: str, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = get_db_session(request)
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
            existing_setup_id, existing_setup = _latest_setup_session_for_user(user_id)
            if existing_setup is not None:
                return {
                    "has_active_session": False,
                    "setup_session_id": existing_setup_id,
                    "setup_status": existing_setup.get("status", "draft"),
                }
            draft_id, draft_session = find_or_create_draft_setup_session(user_id, "de")
            return {
                "has_active_session": False,
                "setup_session_id": draft_id,
                "setup_status": draft_session["status"],
            }

        setup_session_id = find_setup_session_id_for_active_session(user_id, session.id)
        return {
            "has_active_session": True,
            "setup_session_id": setup_session_id,
            "chastity_session": serialize_chastity_session(session),
        }
    finally:
        db.close()


@router.delete("/active")
def kill_active_chastity_session(
    user_id: str, auth_token: str, request: Request, setup_session_id: str | None = None
) -> dict:
    if not getattr(request.app.state.config, "ENABLE_SESSION_KILL", False):
        raise HTTPException(status_code=404, detail="Not found.")

    token_user_id = resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = get_db_session(request)
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
        inferred_setup_session_id = None
        if session is not None:
            inferred_setup_session_id = find_setup_session_id_for_active_session(user_id, session.id)
            turns = db.scalars(select(Turn).where(Turn.session_id == session.id)).all()
            for turn in turns:
                db.delete(turn)
            killed_session_id = session.id
            db.delete(session)
            deleted = True
        db.commit()

        deleted_setup_session = False
        target_setup_session_id = setup_session_id or inferred_setup_session_id
        if target_setup_session_id:
            store = load_sessions()
            setup_session = store.get(target_setup_session_id)
            if setup_session and setup_session.get("user_id") == user_id:
                del store[target_setup_session_id]
                save_sessions(store)
                deleted_setup_session = True

        draft_id, draft_session = find_or_create_draft_setup_session(user_id, "de")
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
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        return serialize_chastity_session(session)
    finally:
        db.close()


@router.get("/{session_id}/turns")
def get_session_turns(session_id: str, request: Request) -> dict:
    db = get_db_session(request)
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
                    "created_at": iso_utc(turn.created_at),
                }
                for turn in turns
            ],
        }
    finally:
        db.close()
