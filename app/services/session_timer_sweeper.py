from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.message import Message
from app.models.session import Session as SessionModel


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def sweep_expired_active_sessions() -> dict:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        active_sessions = db.query(SessionModel).filter(SessionModel.status == "active").all()
        ended = 0

        for session_obj in active_sessions:
            if session_obj.lock_end is None:
                continue
            if _as_utc(session_obj.lock_end) > now:
                continue

            session_obj.status = "completed"
            session_obj.lock_end_actual = now
            db.add(session_obj)
            db.add(
                Message(
                    session_id=session_obj.id,
                    role="assistant",
                    message_type="session_event",
                    content="Session automatisch beendet: geplante Sperrzeit erreicht.",
                )
            )
            ended += 1

        if ended > 0:
            db.commit()

        return {
            "scanned_sessions": len(active_sessions),
            "ended_sessions": ended,
        }
