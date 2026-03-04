import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Request
from sqlalchemy.orm import Session

from chastease.models import ChastitySession, Turn, TurnJob

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="turn-job")


def _run_turn_job(
    *,
    job_id: str,
    session_id: str,
    action: str,
    language: str,
    attachments: list[dict],
    request: Request,
) -> None:
    from chastease.api.runtime import get_db_session
    from chastease.services.narration import generate_ai_narration_for_session
    from sqlalchemy import func, select

    db_factory = request.app.state.db_session_factory
    db: Session = db_factory()
    try:
        job = db.get(TurnJob, job_id)
        if job is None:
            logger.error("TurnJob %s not found", job_id)
            return

        session = db.get(ChastitySession, session_id)
        if session is None:
            job.status = "error"
            job.error = "Session not found"
            job.updated_at = datetime.now(UTC)
            db.add(job)
            db.commit()
            return

        try:
            narration = generate_ai_narration_for_session(db, request, session, action, language, attachments)
        except Exception as exc:
            logger.exception("TurnJob %s LLM call failed", job_id)
            job.status = "error"
            job.error = str(exc)[:500]
            job.updated_at = datetime.now(UTC)
            db.add(job)
            db.commit()
            return

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session_id))
        next_turn_no = (current_turn_no or 0) + 1

        turn = Turn(
            id=str(uuid4()),
            session_id=session_id,
            turn_no=next_turn_no,
            player_action=action,
            ai_narration=narration,
            language=language,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)

        job.status = "done"
        job.turn_id = turn.id
        job.updated_at = datetime.now(UTC)
        db.add(job)
        db.commit()
    except Exception:
        logger.exception("TurnJob %s unexpected failure", job_id)
        try:
            job = db.get(TurnJob, job_id)
            if job and job.status == "pending":
                job.status = "error"
                job.error = "Unexpected internal error"
                job.updated_at = datetime.now(UTC)
                db.add(job)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def submit_turn_job(
    db: Session,
    *,
    session_id: str,
    action: str,
    language: str,
    attachments: list[dict],
    request: Request,
) -> str:
    now = datetime.now(UTC)
    job_id = str(uuid4())
    job = TurnJob(
        id=job_id,
        session_id=session_id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()

    _executor.submit(
        _run_turn_job,
        job_id=job_id,
        session_id=session_id,
        action=action,
        language=language,
        attachments=attachments,
        request=request,
    )
    return job_id
