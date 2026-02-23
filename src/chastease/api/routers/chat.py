import base64
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api.runtime import get_db_session, lang
from chastease.api.schemas import ChatActionExecuteRequest, ChatTurnRequest, ChatVisionReviewRequest
from chastease.models import ChastitySession, Turn
from chastease.services.narration import extract_pending_actions, generate_ai_narration_for_session

router = APIRouter(prefix="/chat", tags=["chat"])

_DURATION_UNIT_SECONDS = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 3600,
    "hours": 3600,
    "day": 86400,
    "days": 86400,
}


def _to_int(value) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid duration values")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return int(value.strip())
    raise ValueError("duration value must be integer-like")


def _normalize_duration_payload(action_type: str, payload: dict) -> dict:
    action = str(action_type or "").strip().lower()
    if action not in {"add_time", "reduce_time"}:
        return dict(payload or {})

    data = dict(payload or {})
    if "seconds" in data:
        seconds = _to_int(data.get("seconds"))
        if seconds <= 0:
            raise HTTPException(status_code=400, detail=f"Action '{action}' requires seconds > 0.")
        return {"seconds": seconds}

    if "amount" in data and "unit" in data:
        amount = _to_int(data.get("amount"))
        unit = str(data.get("unit") or "").strip().lower()
        factor = _DURATION_UNIT_SECONDS.get(unit)
        if factor is None:
            raise HTTPException(
                status_code=400,
                detail="Duration unit must be one of: seconds, minutes, hours, days.",
            )
        seconds = amount * factor
        if seconds <= 0:
            raise HTTPException(status_code=400, detail=f"Action '{action}' requires a positive duration.")
        return {"seconds": seconds}

    # Backward-compatible convenience fields accepted from AI payloads.
    for key in ("minutes", "hours", "days"):
        if key in data:
            amount = _to_int(data.get(key))
            seconds = amount * _DURATION_UNIT_SECONDS[key]
            if seconds <= 0:
                raise HTTPException(status_code=400, detail=f"Action '{action}' requires a positive duration.")
            return {"seconds": seconds}

    raise HTTPException(
        status_code=400,
        detail=(
            f"Action '{action}' requires a duration payload. "
            "Use either {seconds} or {amount, unit} with unit in seconds/minutes/hours/days."
        ),
    )


@router.post("/turn")
def chat_turn(payload: ChatTurnRequest, request: Request) -> dict:
    request_lang = lang(payload.language)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")

    action_text = message

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        narration_raw = generate_ai_narration_for_session(
            db, request, session, action_text, request_lang, payload.attachments
        )
        narration, pending_actions, generated_files = extract_pending_actions(narration_raw)

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session.id))
        next_turn_no = (current_turn_no or 0) + 1
        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=action_text,
            ai_narration=narration,
            language=request_lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
        "pending_actions": pending_actions,
        "generated_files": generated_files,
        "next_state": "awaiting_wearer_action",
    }


@router.post("/vision-review")
def chat_vision_review(payload: ChatVisionReviewRequest, request: Request) -> dict:
    request_lang = lang(payload.language)
    prompt = payload.message.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")
    content_type = payload.picture_content_type.lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="picture_content_type must be image/*")
    if not payload.picture_data_url.startswith(f"data:{content_type};base64,"):
        raise HTTPException(status_code=400, detail="Invalid picture_data_url format.")
    image_b64 = payload.picture_data_url.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="picture too large (max 8MB)")
    attachments = [
        {
            "name": payload.picture_name or "image",
            "type": content_type,
            "size": len(image_bytes),
            "data_url": payload.picture_data_url,
        }
    ]

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        narration_raw = generate_ai_narration_for_session(db, request, session, prompt, request_lang, attachments)
        narration, pending_actions, generated_files = extract_pending_actions(narration_raw)

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session.id))
        next_turn_no = (current_turn_no or 0) + 1
        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=f"{prompt} [image:{payload.picture_name or 'upload'}]",
            ai_narration=narration,
            language=request_lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
        "pending_actions": pending_actions,
        "generated_files": generated_files,
        "next_state": "awaiting_wearer_action",
    }


@router.post("/actions/execute")
def chat_action_execute(payload: ChatActionExecuteRequest, request: Request) -> dict:
    registry = getattr(request.app.state, "tool_registry", None)
    if registry is not None and not registry.is_allowed(payload.action_type, mode="execute"):
        raise HTTPException(status_code=403, detail=f"Tool '{payload.action_type}' is not allowed for execution.")
    normalized_payload = _normalize_duration_payload(payload.action_type, payload.payload)

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        session.updated_at = datetime.now(UTC)
        db.add(session)
        db.commit()
    finally:
        db.close()
    return {
        "executed": True,
        "session_id": payload.session_id,
        "action_type": payload.action_type,
        "payload": normalized_payload,
        "message": "Action execution placeholder completed.",
    }
