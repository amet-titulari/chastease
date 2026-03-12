import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.safety_log import SafetyLog
from app.models.scenario import Scenario
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.services.ai_gateway import get_ai_gateway
from app.services.audit_logger import audit_log
from app.services.context_window import build_context_window
from app.services.prompt_builder import build_prompt_modules

router = APIRouter(prefix="/api/sessions", tags=["chat"])


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class RegenerateMessageRequest(BaseModel):
    user_text: str | None = None


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


def _persist_chat_turn(db: Session, session_id: int, user_text: str, image_bytes: bytes | None = None, image_filename: str | None = None) -> Message:
    session_obj = _load_session(db, session_id)
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    persona_name = persona.name if persona else "Keyholderin"
    safety_mode = _latest_safety_mode(db, session_id)
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()

    hard_limits: list[str] = []
    if profile and profile.hard_limits_json:
        try:
            parsed = json.loads(profile.hard_limits_json)
            if isinstance(parsed, list):
                hard_limits = [str(item).strip().lower() for item in parsed if str(item).strip()]
        except Exception:
            hard_limits = []

    ai = get_ai_gateway()
    prefs: dict = {}
    scenario_title = None
    if profile and profile.preferences_json:
        try:
            prefs = json.loads(profile.preferences_json)
            if isinstance(prefs, dict) and prefs.get("scenario_preset"):
                scenario_title = str(prefs.get("scenario_preset"))[:120]
        except Exception:
            pass
    if scenario_title is None and persona and persona.description:
        scenario_title = persona.description[:120]

    # Load full scenario for phase + lorebook injection
    active_phase: dict | None = None
    matched_lore: list[dict] = []
    scenario_key = prefs.get("scenario_preset") if prefs else None
    if scenario_key:
        db_scenario = db.query(Scenario).filter(Scenario.key == scenario_key).first()
        if db_scenario:
            _phases = json.loads(db_scenario.phases_json or "[]")
            _lorebook = json.loads(db_scenario.lorebook_json or "[]")
        else:
            from app.routers.scenarios import SCENARIO_PRESETS as _SP
            _preset = next((p for p in _SP if p.get("key") == scenario_key), None)
            _phases = _preset.get("phases", []) if _preset else []
            _lorebook = _preset.get("lorebook", []) if _preset else []

        # Active phase: from prefs or default to first
        phase_id = prefs.get("scenario_phase_id") if prefs else None
        if phase_id:
            active_phase = next((p for p in _phases if p.get("phase_id") == phase_id), None)
        if active_phase is None and _phases:
            active_phase = _phases[0]

        # Match lorebook entries by triggers in user_text (top 3 by priority)
        text_lower = user_text.lower()
        for entry in sorted(_lorebook, key=lambda e: e.get("priority", 0), reverse=True):
            if any(str(t).lower() in text_lower for t in entry.get("triggers", [])):
                matched_lore.append(entry)
            if len(matched_lore) >= 3:
                break

    context_rows = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id.asc())
        .all()
    )
    context_items, context_summary = build_context_window(context_rows, max_messages=12)

    # Inject pending tasks into context so the AI knows IDs for fail_task
    pending_tasks = (
        db.query(Task)
        .filter(Task.session_id == session_id, Task.status == "pending")
        .order_by(Task.id.asc())
        .all()
    )
    if pending_tasks:
        tasks_summary = "Offene Tasks: " + "; ".join(
            f"id={t.id} '{t.title}'"
            + (f" (Verifizierung noetig)" if t.requires_verification else "")
            for t in pending_tasks
        )
        context_items = [{"role": "system", "content": tasks_summary, "message_type": "task_context"}] + (context_items or [])

    wearer_nickname = profile.nickname if profile else None
    experience_level = profile.experience_level if profile else None
    wearer_style: str | None = None
    wearer_goal: str | None = None
    wearer_boundary: str | None = None
    if prefs:
        wearer_style = prefs.get("wearer_style")
        wearer_goal = prefs.get("wearer_goal")
        wearer_boundary = prefs.get("wearer_boundary")
    # Fall back to the AuthUser-level setup_boundary if not set on the profile
    if not wearer_boundary:
        from app.models.auth_user import AuthUser as _AuthUser
        _au = db.query(_AuthUser).filter(_AuthUser.active_session_id == session_id).first()
        if _au and _au.setup_boundary:
            wearer_boundary = _au.setup_boundary

    prompt_modules = build_prompt_modules(
        persona_name=persona_name,
        session_status=session_obj.status,
        safety_mode=safety_mode,
        scenario_title=scenario_title,
        wearer_nickname=wearer_nickname,
        experience_level=experience_level,
        wearer_style=wearer_style,
        wearer_goal=wearer_goal,
        wearer_boundary=wearer_boundary,
        persona_system_prompt=persona.system_prompt if persona else None,
        speech_style_tone=persona.speech_style_tone if persona else None,
        speech_style_dominance=persona.speech_style_dominance if persona else None,
        strictness_level=persona.strictness_level if persona else 3,
        hard_limits=hard_limits or None,
        active_phase=active_phase,
        lorebook_entries=matched_lore or None,
    ).render()

    structured = ai.generate_chat_response(
        persona_name=persona_name,
        user_text=user_text,
        prompt_modules=prompt_modules,
        context_items=context_items,
        context_summary=context_summary,
        image_bytes=image_bytes,
        image_filename=image_filename,
    )

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

            # --- fail_task action ---
            if action.get("type") == "fail_task":
                task_id = action.get("task_id")
                if task_id:
                    fail_task = db.query(Task).filter(
                        Task.id == task_id,
                        Task.session_id == session_id,
                        Task.status == "pending",
                    ).first()
                    if fail_task:
                        now = datetime.now(timezone.utc)
                        fail_task.status = "failed"
                        TaskService.apply_task_consequence(
                            db=db,
                            session_obj=session_obj,
                            task=fail_task,
                            now=now,
                        )
                        db.add(fail_task)
                        db.add(Message(
                            session_id=session_id,
                            role="system",
                            content=f"Task '{fail_task.title}' als fehlgeschlagen markiert (KI-Entscheidung).",
                            message_type="task_failed",
                        ))
                continue

            if action.get("type") != "create_task":
                continue
            title = str(action.get("title", "")).strip()[:200]
            if not title:
                continue

            description_value = str(action.get("description")) if action.get("description") else ""
            raw_criteria = str(action.get("verification_criteria") or "")
            searchable = f"{title} {description_value} {raw_criteria}".lower()
            if any(
                limit in searchable
                or any(w in searchable for w in limit.split() if len(w) > 4)
                for limit in hard_limits
            ):
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

            requires_verification = bool(action.get("requires_verification", False))
            verification_criteria_value = action.get("verification_criteria")
            if verification_criteria_value:
                verification_criteria_value = str(verification_criteria_value).strip()[:500] or None

            task = Task(
                session_id=session_id,
                title=title,
                description=(description_value[:2000] if description_value else None),
                deadline_at=deadline_at,
                consequence_type=consequence_type,
                consequence_value=consequence_value,
                requires_verification=requires_verification,
                verification_criteria=verification_criteria_value,
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
    audit_log("chat_turn", session_id=session_id, user_text=user_text[:200], reply_preview=reply_text[:120])
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


_ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/{session_id}/messages/image")
async def send_message_with_image(
    session_id: int,
    content: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict:
    image_bytes: bytes | None = None
    image_filename: str | None = None
    if file is not None:
        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type not in _ALLOWED_IMAGE_MIMES:
            raise HTTPException(status_code=415, detail="Nur Bilddateien sind erlaubt (JPEG, PNG, GIF, WEBP).")
        raw = await file.read()
        if len(raw) > _MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Bild ist zu groß (max. 10 MB).")
        image_bytes = raw
        image_filename = file.filename

    user_text = content.strip() or "(Bild ohne Text)"
    assistant_msg = _persist_chat_turn(
        db=db,
        session_id=session_id,
        user_text=user_text,
        image_bytes=image_bytes,
        image_filename=image_filename,
    )
    return {
        "session_id": session_id,
        "reply": assistant_msg.content,
        "reply_message_id": assistant_msg.id,
    }


@router.post("/{session_id}/messages/regenerate")
def regenerate_last_message(
    session_id: int,
    payload: RegenerateMessageRequest,
    db: Session = Depends(get_db),
) -> dict:
    _load_session(db, session_id)
    user_text = payload.user_text
    if not user_text:
        row = (
            db.query(Message)
            .filter(Message.session_id == session_id, Message.role == "user")
            .order_by(Message.id.desc())
            .first()
        )
        if row is None:
            raise HTTPException(status_code=400, detail="No user message available for regeneration")
        user_text = row.content

    assistant_msg = _persist_chat_turn(db=db, session_id=session_id, user_text=user_text)
    assistant_msg.message_type = "chat_regenerated"
    db.commit()
    db.refresh(assistant_msg)
    return {
        "session_id": session_id,
        "reply": assistant_msg.content,
        "reply_message_id": assistant_msg.id,
        "message_type": assistant_msg.message_type,
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
