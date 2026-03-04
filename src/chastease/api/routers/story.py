from fastapi import APIRouter, HTTPException, Request

from chastease.api.runtime import get_db_session, lang, t
from chastease.api.schemas import StoryTurnRequest
from chastease.compat.rate_limit import Limiter, get_remote_address
from chastease.models import ChastitySession, Turn, TurnJob
from chastease.services.jobs import submit_turn_job

router = APIRouter(prefix="/story", tags=["story"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/turn")
@limiter.limit("30/minute")
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

        job_id = submit_turn_job(
            db,
            session_id=session.id,
            action=action,
            language=request_lang,
            attachments=[],
            request=request,
        )
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "job_id": job_id,
        "status": "pending",
    }


@router.get("/turn/job/{job_id}")
@limiter.limit("60/minute")
def poll_turn_job(job_id: str, request: Request) -> dict:
    db = get_db_session(request)
    try:
        job = db.get(TurnJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")

        response: dict = {
            "job_id": job_id,
            "session_id": job.session_id,
            "status": job.status,
        }

        if job.status == "done" and job.turn_id:
            turn = db.get(Turn, job.turn_id)
            if turn:
                response["turn_no"] = turn.turn_no
                response["narration"] = turn.ai_narration
                response["player_action"] = turn.player_action

        if job.status == "error":
            response["error"] = job.error

        return response
    finally:
        db.close()
