from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.models.message import Message
from app.models.persona import Persona
from app.models.session import Session as SessionModel


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_reminder(persona_name: str, session_obj: SessionModel, now: datetime) -> str:
    if session_obj.lock_end is None:
        return f"{persona_name}: Bleib fokussiert. Ich erwarte jetzt einen kurzen Statusbericht."

    remaining_seconds = int((_as_utc(session_obj.lock_end) - now).total_seconds())
    if remaining_seconds > 0:
        remaining_minutes = max(1, remaining_seconds // 60)
        return (
            f"{persona_name}: Disziplin halten. Noch ca. {remaining_minutes} Minuten in dieser Phase. "
            "Melde dich mit deinem aktuellen Zustand."
        )

    return f"{persona_name}: Die geplante Zeit ist erreicht. Warte auf meine naechste Anweisung."


def sweep_proactive_messages_for_active_sessions() -> dict:
    now = datetime.now(timezone.utc)
    cooldown = timedelta(seconds=max(settings.proactive_messages_cooldown_seconds, 0))

    with SessionLocal() as db:
        active_sessions = db.query(SessionModel).filter(SessionModel.status == "active").all()
        sent_count = 0

        for session_obj in active_sessions:
            last_assistant = (
                db.query(Message)
                .filter(Message.session_id == session_obj.id, Message.role == "assistant")
                .order_by(Message.id.desc())
                .first()
            )
            if last_assistant is not None and _as_utc(last_assistant.created_at) > (now - cooldown):
                continue

            persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
            persona_name = persona.name if persona else "Keyholderin"
            reminder = Message(
                session_id=session_obj.id,
                role="assistant",
                content=_build_reminder(persona_name, session_obj, now),
                message_type="proactive_reminder",
            )
            db.add(reminder)
            sent_count += 1

        if sent_count > 0:
            db.commit()

        return {
            "scanned_sessions": len(active_sessions),
            "sent_messages": sent_count,
        }
