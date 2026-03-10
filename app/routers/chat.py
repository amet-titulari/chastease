import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.message import Message
from app.models.persona import Persona
from app.models.safety_log import SafetyLog
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.services.ai_gateway import get_ai_gateway

router = APIRouter(prefix="/api/sessions", tags=["chat"])


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)


def _load_session(db: Session, session_id: int) -> SessionModel:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


def _fresh_ws_token(session_id: int) -> str | None:
    with SessionLocal() as fresh_db:
        row = fresh_db.query(SessionModel).filter(SessionModel.id == session_id).first()
        return row.ws_auth_token if row else None


def _latest_safety_mode(db: Session, session_id: int) -> str | None:
    row = (
        db.query(SafetyLog)
        .filter(SafetyLog.session_id == session_id)
        .order_by(SafetyLog.id.desc())
        .first()
    )
    return row.event_type if row else None


def _assistant_reply(persona_name: str, user_text: str, safety_mode: str | None, session_status: str) -> str:
    if session_status in {"safeword_stopped", "emergency_stopped"}:
        return (
            f"{persona_name}: Safety-Stop ist aktiv. Wir bleiben bei Stabilisierung und Sicherheitspruefung. "
            "Es folgen keine spielbezogenen Anweisungen."
        )

    if safety_mode == "red" or session_status == "paused":
        return (
            f"{persona_name}: Rot ist aktiv. Session bleibt pausiert. "
            "Atme ruhig, trink Wasser und bestaetige mir kurz, wenn du stabil bist."
        )

    if safety_mode == "yellow":
        return (
            f"{persona_name}: Gelb ist registriert. Ich schalte in Fuersorge-Modus. "
            f"Danke fuer dein Update: '{user_text}'. Wir reduzieren Intensitaet und bleiben bei klaren, ruhigen Schritten."
        )

    return f"{persona_name}: Ich habe dich gehoert. Du sagtest: '{user_text}'. Bleib diszipliniert."


def _persist_chat_turn(db: Session, session_id: int, user_text: str) -> Message:
    session_obj = _load_session(db, session_id)
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    persona_name = persona.name if persona else "Keyholderin"
    safety_mode = _latest_safety_mode(db, session_id)

    ai = get_ai_gateway()
    structured = ai.generate_chat_response(persona_name=persona_name, user_text=user_text)

    reply_text = structured.message
    if safety_mode == "yellow" or safety_mode == "red" or session_obj.status in {
        "paused",
        "safeword_stopped",
        "emergency_stopped",
    }:
        reply_text = _assistant_reply(
            persona_name,
            user_text,
            safety_mode=safety_mode,
            session_status=session_obj.status,
        )

    created_task_ids: list[int] = []
    if reply_text == structured.message:
        for action in structured.actions:
            if not isinstance(action, dict):
                continue
            if action.get("type") != "create_task":
                continue
            title = str(action.get("title", "")).strip()[:200]
            if not title:
                continue

            deadline_minutes = action.get("deadline_minutes")
            deadline_at = None
            if isinstance(deadline_minutes, int) and deadline_minutes > 0:
                deadline_at = datetime.now(timezone.utc) + timedelta(minutes=deadline_minutes)

            consequence_type = action.get("consequence_type")
            if consequence_type is not None:
                consequence_type = str(consequence_type)
            consequence_value = action.get("consequence_value")
            if not isinstance(consequence_value, int):
                consequence_value = None

            task = Task(
                session_id=session_id,
                title=title,
                description=(str(action.get("description"))[:2000] if action.get("description") else None),
                deadline_at=deadline_at,
                consequence_type=consequence_type,
                consequence_value=consequence_value,
            )
            db.add(task)
            db.flush()
            created_task_ids.append(task.id)

    user_msg = Message(session_id=session_id, role="user", content=user_text, message_type="chat")
    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=reply_text,
        message_type="chat",
    )

    if created_task_ids:
        summary = ", ".join(str(item) for item in created_task_ids)
        db.add(
            Message(
                session_id=session_id,
                role="system",
                content=f"Tasks erstellt: {summary}",
                message_type="task_assigned",
            )
        )

    db.add(user_msg)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


def _latest_assistant_message_id(db: Session, session_id: int) -> int:
    row = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.role == "assistant")
        .order_by(Message.id.desc())
        .first()
    )
    return row.id if row else 0


async def _push_new_assistant_messages(
    websocket: WebSocket,
    db: Session,
    session_id: int,
    last_sent_assistant_id: int,
) -> int:
    rows = (
        db.query(Message)
        .filter(
            Message.session_id == session_id,
            Message.role == "assistant",
            Message.id > last_sent_assistant_id,
        )
        .order_by(Message.id.asc())
        .all()
    )
    for row in rows:
        await websocket.send_json(
            {
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "assistant": row.content,
                "message_id": row.id,
                "message_type": row.message_type,
            }
        )
        last_sent_assistant_id = row.id
    return last_sent_assistant_id


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timer_snapshot(session_obj: SessionModel, now: datetime) -> tuple[int, bool]:
    if session_obj.lock_end is None:
        return 0, bool(session_obj.timer_frozen)
    anchor = now
    if session_obj.timer_frozen and session_obj.freeze_start is not None:
        anchor = _as_utc(session_obj.freeze_start)
    remaining = max(0, int((_as_utc(session_obj.lock_end) - anchor).total_seconds()))
    return remaining, bool(session_obj.timer_frozen)


@router.get("/{session_id}/messages")
def list_messages(session_id: int, db: Session = Depends(get_db)) -> dict:
    _load_session(db, session_id)
    rows = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id.asc()).all()
    return {
        "session_id": session_id,
        "items": [
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "message_type": row.message_type,
                "created_at": str(row.created_at),
            }
            for row in rows
        ],
    }


@router.post("/{session_id}/messages")
def send_message(session_id: int, payload: SendMessageRequest, db: Session = Depends(get_db)) -> dict:
    assistant_msg = _persist_chat_turn(db=db, session_id=session_id, user_text=payload.content)
    return {
        "session_id": session_id,
        "reply": assistant_msg.content,
        "reply_message_id": assistant_msg.id,
    }


@router.websocket("/{session_id}/chat/ws")
async def chat_ws(websocket: WebSocket, session_id: int):
    await websocket.accept()
    db = SessionLocal()
    try:
        session_obj = _load_session(db, session_id)
        supplied_token = websocket.query_params.get("token")
        if not supplied_token or supplied_token != session_obj.ws_auth_token:
            await websocket.close(code=1008, reason="Invalid websocket token")
            return
        token_at_connect = supplied_token
        stream_timer = websocket.query_params.get("stream_timer") in {"1", "true", "yes"}
        last_timer_remaining: int | None = None
        last_timer_frozen: bool | None = None

        last_sent_assistant_id = _latest_assistant_message_id(db, session_id)
        while True:
            if _fresh_ws_token(session_id) != token_at_connect:
                await websocket.close(code=1008, reason="Websocket token rotated")
                return

            try:
                user_text = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                if _fresh_ws_token(session_id) != token_at_connect:
                    await websocket.close(code=1008, reason="Websocket token rotated")
                    return
                assistant_msg = _persist_chat_turn(db=db, session_id=session_id, user_text=user_text)
                await websocket.send_json(
                    {
                        "session_id": session_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "assistant": assistant_msg.content,
                        "message_id": assistant_msg.id,
                        "message_type": assistant_msg.message_type,
                    }
                )
                last_sent_assistant_id = assistant_msg.id
            except TimeoutError:
                pass

            last_sent_assistant_id = await _push_new_assistant_messages(
                websocket=websocket,
                db=db,
                session_id=session_id,
                last_sent_assistant_id=last_sent_assistant_id,
            )

            if stream_timer:
                current = _load_session(db, session_id)
                remaining, frozen = _timer_snapshot(current, datetime.now(timezone.utc))
                if remaining != last_timer_remaining or frozen != last_timer_frozen:
                    await websocket.send_json(
                        {
                            "session_id": session_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "message_type": "timer_tick",
                            "remaining_seconds": remaining,
                            "timer_frozen": frozen,
                        }
                    )
                    last_timer_remaining = remaining
                    last_timer_frozen = frozen
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
