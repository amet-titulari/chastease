import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.item import Item
from app.models.safety_log import SafetyLog
from app.models.scenario import Scenario
from app.models.scenario_item import ScenarioItem
from app.models.session import Session as SessionModel
from app.models.session_item import SessionItem
from app.models.task import Task
from app.services.ai_gateway import get_ai_gateway
from app.services.audit_logger import audit_log
from app.services.context_window import build_context_window
from app.services.prompt_builder import build_prompt_modules
from app.services.task_service import TaskService
from app.services.transcription_service import transcribe_audio

logger = logging.getLogger(__name__)

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


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fmt_deadline_for_context(value: datetime | None) -> str:
    utc_value = _as_utc(value)
    if utc_value is None:
        return "keine"
    local_value = utc_value.astimezone()
    return (
        f"utc={utc_value.isoformat(timespec='seconds')}; "
        f"local={local_value.isoformat(timespec='seconds')}"
    )


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

    ai = get_ai_gateway(session_obj=session_obj)
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

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone()
    time_context = (
        "Aktuelle Zeit fuer Deadlines: "
        f"utc={now_utc.isoformat(timespec='seconds')}; "
        f"local={now_local.isoformat(timespec='seconds')}; "
        f"tz_name={now_local.tzname() or 'unknown'}"
    )
    context_items = [{"role": "system", "content": time_context, "message_type": "time_context"}] + (context_items or [])

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
            + f" (Deadline: {_fmt_deadline_for_context(t.deadline_at)})"
            + (f" (Verifizierung noetig)" if t.requires_verification else "")
            for t in pending_tasks
        )
        context_items = [{"role": "system", "content": tasks_summary, "message_type": "task_context"}] + (context_items or [])

    session_inventory_rows = (
        db.query(SessionItem, Item)
        .join(Item, Item.id == SessionItem.item_id)
        .filter(SessionItem.session_id == session_id)
        .order_by(Item.name.asc())
        .all()
    )
    if session_inventory_rows:
        inventory_summary = "Session-Inventar: " + "; ".join(
            f"{item.name} x{session_item.quantity} [{session_item.status}]"
            + (" (equipped)" if session_item.is_equipped else "")
            for session_item, item in session_inventory_rows
        )
        context_items = [{"role": "system", "content": inventory_summary, "message_type": "inventory_context"}] + (context_items or [])
    elif scenario_key:
        scenario_row = db.query(Scenario).filter(Scenario.key == scenario_key).first()
        if scenario_row:
            scenario_inventory_rows = (
                db.query(ScenarioItem, Item)
                .join(Item, Item.id == ScenarioItem.item_id)
                .filter(ScenarioItem.scenario_id == scenario_row.id)
                .order_by(Item.name.asc())
                .all()
            )
            if scenario_inventory_rows:
                inventory_summary = "Scenario-Inventar (Template): " + "; ".join(
                    f"{item.name} x{scenario_item.default_quantity}"
                    + (" [required]" if scenario_item.is_required else "")
                    for scenario_item, item in scenario_inventory_rows
                )
                context_items = [{"role": "system", "content": inventory_summary, "message_type": "inventory_context"}] + (context_items or [])

    wearer_nickname = profile.nickname if profile else None
    experience_level = profile.experience_level if profile else None
    wearer_style: str | None = None
    wearer_goal: str | None = None
    wearer_boundary: str | None = None
    if prefs:
        wearer_style = prefs.get("wearer_style")
        wearer_goal = prefs.get("wearer_goal")
        wearer_boundary = prefs.get("wearer_boundary")

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
    created_task_details: list[str] = []
    updated_task_details: list[str] = []
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

            if action.get("type") == "update_task":
                task_id = action.get("task_id")
                if not isinstance(task_id, int) or task_id <= 0:
                    continue

                target_task = db.query(Task).filter(
                    Task.id == task_id,
                    Task.session_id == session_id,
                    Task.status.notin_(["completed", "failed"]),
                ).first()
                if not target_task:
                    continue

                changed_fields: list[str] = []

                if action.get("title") is not None:
                    next_title = str(action.get("title") or "").strip()[:200]
                    if next_title and next_title != target_task.title:
                        target_task.title = next_title
                        changed_fields.append("title")

                if action.get("description") is not None:
                    raw_description = str(action.get("description") or "").strip()
                    next_description = raw_description[:2000] if raw_description else None
                    if next_description != target_task.description:
                        target_task.description = next_description
                        changed_fields.append("description")

                if "deadline_minutes" in action:
                    deadline_minutes = action.get("deadline_minutes")
                    if isinstance(deadline_minutes, int) and deadline_minutes > 0:
                        target_task.deadline_at = datetime.now(timezone.utc) + timedelta(minutes=deadline_minutes)
                        changed_fields.append(f"deadline(+{deadline_minutes}m)")
                    else:
                        target_task.deadline_at = None
                        changed_fields.append("deadline(null)")

                if changed_fields:
                    db.add(target_task)
                    updated_task_details.append(
                        f"#{target_task.id} '{target_task.title}' ({', '.join(changed_fields)}; "
                        f"Deadline: {_fmt_deadline_for_context(target_task.deadline_at)})"
                    )
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
                logger.info("Task '%s': deadline_minutes=%d → deadline_at=%s", title, deadline_minutes, deadline_at.isoformat())
            else:
                logger.info("Task '%s': keine Deadline (deadline_minutes=%s)", title, deadline_minutes)

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
            created_task_details.append(
                f"#{task.id} '{title}' (Deadline: {deadline_at.isoformat() if deadline_at else 'keine'})"
            )

    user_msg = Message(session_id=session_id, role="user", content=user_text, message_type="chat")
    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=reply_text,
        message_type="chat",
    )

    if created_task_ids:
        summary = "; ".join(created_task_details)
        db.add(
            Message(
                session_id=session_id,
                role="system",
                content=f"Tasks erstellt: {summary}",
                message_type="task_assigned",
            )
        )

    if updated_task_details:
        db.add(
            Message(
                session_id=session_id,
                role="system",
                content=f"Tasks aktualisiert: {'; '.join(updated_task_details)}",
                message_type="task_updated",
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
_ALLOWED_AUDIO_MIMES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 20 MB


def _parse_upload_mime(file: UploadFile) -> str:
    return (file.content_type or "").split(";")[0].strip().lower()


async def _build_chat_media_payload(content: str, file: UploadFile | None) -> tuple[str, bytes | None, str | None, str | None, bytes | None, str | None, str | None]:
    image_bytes: bytes | None = None
    image_filename: str | None = None
    media_kind: str | None = None
    audio_bytes: bytes | None = None
    audio_filename: str | None = None
    audio_mime: str | None = None

    if file is not None:
        content_type = _parse_upload_mime(file)
        raw = await file.read()
        if content_type in _ALLOWED_IMAGE_MIMES:
            if len(raw) > _MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Bild ist zu groß (max. 10 MB).")
            image_bytes = raw
            image_filename = file.filename
            media_kind = "image"
        elif content_type in _ALLOWED_AUDIO_MIMES:
            if len(raw) > _MAX_AUDIO_BYTES:
                raise HTTPException(status_code=413, detail="Audio ist zu groß (max. 20 MB).")
            media_kind = "audio"
            audio_bytes = raw
            audio_filename = file.filename or "audio-upload"
            audio_mime = content_type
        else:
            raise HTTPException(
                status_code=415,
                detail="Nur Bild- oder Audiodateien sind erlaubt (JPEG, PNG, GIF, WEBP, MP3, M4A, WAV, OGG, WEBM, FLAC).",
            )

    user_text = content.strip()
    if media_kind == "audio":
        # Transcription is added by endpoint logic (provider-specific).
        pass
    elif not user_text and media_kind == "image":
        user_text = "(Bild ohne Text)"
    elif not user_text:
        user_text = "(Nachricht ohne Text)"

    return user_text, image_bytes, image_filename, media_kind, audio_bytes, audio_filename, audio_mime


@router.post("/{session_id}/messages/media")
async def send_message_with_media(
    session_id: int,
    content: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict:
    user_text, image_bytes, image_filename, media_kind, audio_bytes, audio_filename, audio_mime = await _build_chat_media_payload(content=content, file=file)
    transcript_text = None
    transcription_status = None

    if media_kind == "audio" and audio_bytes is not None:
        session_obj = _load_session(db, session_id)
        result = transcribe_audio(
            db=db,
            audio_bytes=audio_bytes,
            filename=audio_filename or "audio-upload",
            mime_type=audio_mime or "application/octet-stream",
            session_obj=session_obj,
        )
        transcription_status = result.status
        if result.status == "ok" and result.text:
            transcript_text = result.text
            if user_text:
                user_text = f"{user_text}\n\n[Audio-Transkript]\n{result.text}"
            else:
                user_text = result.text
        else:
            audio_note = f"[Audio-Upload: {audio_filename or 'audio'}]"
            if result.error:
                audio_note += f" [Transkript nicht verfügbar: {result.error}]"
            user_text = f"{user_text}\n\n{audio_note}".strip() if user_text else audio_note
    assistant_msg = _persist_chat_turn(
        db=db,
        session_id=session_id,
        user_text=user_text,
        image_bytes=image_bytes,
        image_filename=image_filename,
    )
    response_message_type = "chat"
    if media_kind == "image":
        response_message_type = "chat_image"
    elif media_kind == "audio":
        response_message_type = "chat_audio"
    response = {
        "session_id": session_id,
        "reply": assistant_msg.content,
        "reply_message_id": assistant_msg.id,
        "message_type": response_message_type,
    }
    if media_kind == "audio":
        response["transcription_status"] = transcription_status or "not-requested"
        response["transcript"] = transcript_text
    return response


@router.post("/{session_id}/messages/image")
async def send_message_with_image(
    session_id: int,
    content: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict:
    # Backward-compatible alias for older frontend clients.
    return await send_message_with_media(session_id=session_id, content=content, file=file, db=db)


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
