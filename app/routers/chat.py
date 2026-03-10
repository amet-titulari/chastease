import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.message import Message
from app.models.persona import Persona
from app.models.session import Session as SessionModel

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


def _assistant_reply(persona_name: str, user_text: str) -> str:
    return f"{persona_name}: Ich habe dich gehoert. Du sagtest: '{user_text}'. Bleib diszipliniert."


def _persist_chat_turn(db: Session, session_id: int, user_text: str) -> Message:
    session_obj = _load_session(db, session_id)
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    persona_name = persona.name if persona else "Keyholderin"

    user_msg = Message(session_id=session_id, role="user", content=user_text, message_type="chat")
    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=_assistant_reply(persona_name, user_text),
        message_type="chat",
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
