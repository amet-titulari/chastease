from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api import routes as legacy
from chastease.api.schemas import StoryTurnRequest
from chastease.models import ChastitySession, Turn

router = APIRouter(prefix="/story", tags=["story"])


@router.post("/turn")
def story_turn(payload: StoryTurnRequest, request: Request) -> dict:
    lang = legacy._lang(payload.language)
    action = payload.action.strip()
    if not action:
        raise HTTPException(status_code=400, detail=legacy._t(lang, "action_required"))
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="Field 'session_id' is required.")

    db = legacy._get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        narration = legacy._generate_ai_narration_for_session(db, request, session, action, lang)

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session.id))
        next_turn_no = (current_turn_no or 0) + 1

        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=action,
            ai_narration=narration,
            language=lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
    }
