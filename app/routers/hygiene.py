from datetime import datetime, timedelta, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hygiene_opening import HygieneOpening
from app.models.player_profile import PlayerProfile
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


def _count_openings_since(db: Session, session_id: int, start_ts: datetime) -> int:
    return (
        db.query(HygieneOpening)
        .filter(
            HygieneOpening.session_id == session_id,
            HygieneOpening.opened_at.is_not(None),
            HygieneOpening.opened_at >= start_ts,
        )
        .count()
    )


def _quota_payload(db: Session, session_obj: SessionModel, now: datetime) -> dict:
    limits = {
        "daily": session_obj.hygiene_limit_daily,
        "weekly": session_obj.hygiene_limit_weekly,
        "monthly": session_obj.hygiene_limit_monthly,
    }
    used = {
        "daily": _count_openings_since(db, session_obj.id, HygieneService.period_start("day", now)),
        "weekly": _count_openings_since(db, session_obj.id, HygieneService.period_start("week", now)),
        "monthly": _count_openings_since(db, session_obj.id, HygieneService.period_start("month", now)),
    }

    def _remaining(key: str) -> int | None:
        limit = limits[key]
        if limit is None:
            return None
        return max(0, limit - used[key])

    def _next_period_start(period: str) -> datetime:
        start = HygieneService.period_start(period, now)
        if period == "day":
            return start + timedelta(days=1)
        if period == "week":
            return start + timedelta(days=7)
        if period == "month":
            if start.month == 12:
                return start.replace(year=start.year + 1, month=1)
            return start.replace(month=start.month + 1)
        raise ValueError(f"Unsupported period: {period}")

    next_allowed_at: dict[str, str | None] = {"daily": None, "weekly": None, "monthly": None}
    blocking_times: list[datetime] = []
    for period_key, period_name in (("daily", "day"), ("weekly", "week"), ("monthly", "month")):
        remaining = _remaining(period_key)
        if remaining is not None and remaining <= 0:
            next_at = _next_period_start(period_name)
            next_allowed_at[period_key] = next_at.isoformat()
            blocking_times.append(next_at)

    next_allowed_at["overall"] = max(blocking_times).isoformat() if blocking_times else None

    return {
        "limits": limits,
        "used": used,
        "remaining": {
            "daily": _remaining("daily"),
            "weekly": _remaining("weekly"),
            "monthly": _remaining("monthly"),
        },
        "next_allowed_at": next_allowed_at,
    }


def _quota_exceeded(quota: dict) -> bool:
    for key in ("daily", "weekly", "monthly"):
        remaining = quota["remaining"][key]
        if remaining is not None and remaining <= 0:
            return True
    return False


def _effective_hygiene_max_duration_seconds(db: Session, session_obj: SessionModel) -> int:
    if isinstance(session_obj.hygiene_opening_max_duration_seconds, int) and session_obj.hygiene_opening_max_duration_seconds > 0:
        return session_obj.hygiene_opening_max_duration_seconds

    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if player:
        try:
            prefs = json.loads(player.preferences_json or "{}")
            if isinstance(prefs, dict):
                candidate = prefs.get("hygiene_opening_max_duration_seconds")
                if isinstance(candidate, (int, float)) and int(candidate) > 0:
                    return int(candidate)
        except Exception:
            pass

    return settings.hygiene_opening_max_duration_seconds


def _effective_hygiene_overdue_penalty_seconds(db: Session, session_obj: SessionModel) -> int:
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if player:
        try:
            reaction = json.loads(player.reaction_patterns_json or "{}")
            if isinstance(reaction, dict):
                candidate = reaction.get("default_penalty_seconds")
                if isinstance(candidate, (int, float)) and int(candidate) > 0:
                    return int(candidate)
        except Exception:
            pass
    return settings.hygiene_overdue_penalty_seconds


@router.get("/{session_id}/hygiene/quota")
def get_hygiene_quota(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc)
    return {
        "session_id": session_id,
        **_quota_payload(db=db, session_obj=session_obj, now=now),
    }


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

    max_duration = _effective_hygiene_max_duration_seconds(db=db, session_obj=session_obj)
    if payload.duration_seconds > max_duration:
        raise HTTPException(
            status_code=422,
            detail=f"Hygiene opening duration exceeds allowed maximum ({max_duration} seconds)",
        )

    now = datetime.now(timezone.utc)
    quota = _quota_payload(db=db, session_obj=session_obj, now=now)
    if _quota_exceeded(quota):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "hygiene_quota_reached",
                "message": "Hygiene opening quota reached",
                "quota": quota,
            },
        )

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
        "quota": _quota_payload(db=db, session_obj=session_obj, now=datetime.now(timezone.utc)),
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
                session_obj = db.query(SessionModel).filter(SessionModel.id == opening.session_id).first()
                min_penalty_seconds = _effective_hygiene_overdue_penalty_seconds(db=db, session_obj=session_obj) if session_obj else settings.hygiene_overdue_penalty_seconds
                penalty_seconds = max(min_penalty_seconds, status.overrun_seconds)
                opening.penalty_seconds = penalty_seconds
                opening.penalty_applied_at = datetime.now(timezone.utc)

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

    # If the opening was started with a seal, a new seal number is mandatory
    if opening.old_seal_number and not payload.new_seal_number:
        raise HTTPException(
            status_code=422,
            detail="Neue Plombennummer ist erforderlich (Öffnung wurde mit Plombe gestartet).",
        )

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
