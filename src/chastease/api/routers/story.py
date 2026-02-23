from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api.runtime import get_db_session, lang, t
from chastease.api.schemas import StoryTurnRequest
from chastease.models import ChastitySession, Turn
from chastease.services.narration import generate_ai_narration_for_session

router = APIRouter(prefix="/story", tags=["story"])


@router.post("/turn")
def story_turn(payload: StoryTurnRequest, request: Request) -> dict:
    request_lang = lang(payload.language)
    action = payload.action.strip()
    if not action:
        raise HTTPException(status_code=400, detail=t(request_lang, "action_required"))
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="Field 'session_id' is required.")

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        narration = generate_ai_narration_for_session(db, request, session, action, request_lang)

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session.id))
        next_turn_no = (current_turn_no or 0) + 1

        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=action,
            ai_narration=narration,
            language=request_lang,
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
