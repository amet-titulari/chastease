from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hygiene_opening import HygieneOpening
from app.models.seal_history import SealHistory
from app.models.session import Session as SessionModel
from app.config import settings
from app.services.hygiene_service import HygieneService

router = APIRouter(prefix="/api/sessions", tags=["hygiene"])


class HygieneOpenRequest(BaseModel):
    duration_seconds: int = Field(default=900, ge=60)
    old_seal_number: str | None = None


class RelockRequest(BaseModel):
    new_seal_number: str | None = None


@router.post("/{session_id}/hygiene/openings")
def request_hygiene_opening(
    session_id: int,
    payload: HygieneOpenRequest,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_obj.status != "active":
        raise HTTPException(status_code=400, detail="Session must be active")

    now = datetime.now(timezone.utc)
    due_back_at = HygieneService.calculate_due_back(now, payload.duration_seconds)
    opening = HygieneOpening(
        session_id=session_id,
        approved_at=now,
        opened_at=now,
        due_back_at=due_back_at,
        status="active",
        old_seal_number=payload.old_seal_number,
    )
    db.add(opening)
    db.flush()

    if payload.old_seal_number:
        db.add(
            SealHistory(
                session_id=session_id,
                hygiene_opening_id=opening.id,
                seal_number=payload.old_seal_number,
                status="destroyed",
                note="Seal opened for hygiene",
            )
        )

    db.commit()
    db.refresh(opening)

    return {
        "opening_id": opening.id,
        "status": opening.status,
        "due_back_at": str(opening.due_back_at),
    }


@router.get("/{session_id}/hygiene/openings/{opening_id}")
def hygiene_opening_status(
    session_id: int,
    opening_id: int,
    db: Session = Depends(get_db),
) -> dict:
    opening = (
        db.query(HygieneOpening)
        .filter(HygieneOpening.session_id == session_id, HygieneOpening.id == opening_id)
        .first()
    )
    if not opening:
        raise HTTPException(status_code=404, detail="Hygiene opening not found")

    if opening.status == "active" and opening.due_back_at is not None:
        status = HygieneService.evaluate_countdown(opening.due_back_at)
        if status.is_overdue:
            opening.status = "overdue"
            opening.overrun_seconds = status.overrun_seconds
            if opening.penalty_applied_at is None:
                penalty_seconds = max(settings.hygiene_overdue_penalty_seconds, status.overrun_seconds)
                opening.penalty_seconds = penalty_seconds
                opening.penalty_applied_at = datetime.now(timezone.utc)

                session_obj = db.query(SessionModel).filter(SessionModel.id == opening.session_id).first()
                if session_obj and session_obj.lock_end is not None:
                    session_obj.lock_end = session_obj.lock_end + timedelta(seconds=penalty_seconds)
                    db.add(session_obj)

            db.add(opening)
            db.commit()
            db.refresh(opening)

    return {
        "opening_id": opening.id,
        "status": opening.status,
        "due_back_at": str(opening.due_back_at) if opening.due_back_at else None,
        "overrun_seconds": opening.overrun_seconds,
        "penalty_seconds": opening.penalty_seconds,
    }


@router.post("/{session_id}/hygiene/openings/{opening_id}/relock")
def relock_hygiene_opening(
    session_id: int,
    opening_id: int,
    payload: RelockRequest,
    db: Session = Depends(get_db),
) -> dict:
    opening = (
        db.query(HygieneOpening)
        .filter(HygieneOpening.session_id == session_id, HygieneOpening.id == opening_id)
        .first()
    )
    if not opening:
        raise HTTPException(status_code=404, detail="Hygiene opening not found")

    if opening.status not in {"active", "overdue"}:
        raise HTTPException(status_code=400, detail="Hygiene opening is not relockable")

    now = datetime.now(timezone.utc)
    overrun_seconds = 0
    if opening.due_back_at is not None:
        countdown = HygieneService.evaluate_countdown(opening.due_back_at, now=now)
        overrun_seconds = countdown.overrun_seconds

    if overrun_seconds > 0 and opening.penalty_applied_at is None:
        penalty_seconds = max(settings.hygiene_overdue_penalty_seconds, overrun_seconds)
        opening.penalty_seconds = penalty_seconds
        opening.penalty_applied_at = now
        session_obj = db.query(SessionModel).filter(SessionModel.id == opening.session_id).first()
        if session_obj and session_obj.lock_end is not None:
            session_obj.lock_end = session_obj.lock_end + timedelta(seconds=penalty_seconds)
            db.add(session_obj)

    opening.relocked_at = now
    opening.status = "closed"
    opening.overrun_seconds = overrun_seconds
    opening.new_seal_number = payload.new_seal_number

    if payload.new_seal_number:
        db.add(
            SealHistory(
                session_id=session_id,
                hygiene_opening_id=opening.id,
                seal_number=payload.new_seal_number,
                status="active",
                note="Seal re-applied after hygiene",
            )
        )

    db.add(opening)
    db.commit()
    db.refresh(opening)

    return {
        "opening_id": opening.id,
        "status": opening.status,
        "overrun_seconds": opening.overrun_seconds,
        "penalty_seconds": opening.penalty_seconds,
        "new_seal_number": opening.new_seal_number,
    }
