from pathlib import Path
from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.models.message import Message
from app.models.verification import Verification
from app.services.image_stamp import stamp_verification_proof
from app.services.session_access import get_owned_session
from app.services.task_service import TaskService
from app.services.verification_analysis import analyze_verification

router = APIRouter(prefix="/api/sessions", tags=["verification"])


class VerificationRequest(BaseModel):
    requested_seal_number: str | None = None
    linked_task_id: int | None = None
    verification_criteria: str | None = None


def _timestamp_slug(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%d-%H%M")


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "upload.jpg").suffix.lower()
    if not suffix:
        return ".jpg"
    if len(suffix) > 10 or any(ch in suffix for ch in ("/", "\\", " ")):
        return ".jpg"
    return suffix


def _chat_verification_filename(
    session_id: int,
    verification_id: int,
    filename: str | None,
    linked_task_id: int | None = None,
) -> str:
    stamp = _timestamp_slug()
    suffix = _safe_suffix(filename)
    task_part = linked_task_id if isinstance(linked_task_id, int) and linked_task_id > 0 else verification_id
    return f"session{session_id}-chat-task{task_part}-{stamp}{suffix}"


def _verification_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    media_root = Path(settings.media_dir).resolve()
    candidate = Path(image_path)
    if not candidate.is_absolute():
        candidate = media_root / candidate
    try:
        rel = candidate.resolve().relative_to(media_root)
    except (ValueError, OSError):
        return None
    rel_posix = rel.as_posix()
    return f"/media/{rel_posix}"


def _compact_keywords(text: str | None, *, limit: int = 4) -> list[str]:
    stopwords = {
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem", "und", "oder", "mit", "ohne",
        "fuer", "fur", "bei", "von", "auf", "aus", "nach", "vor", "hinter", "ueber", "unter", "zwischen", "nicht",
        "muss", "soll", "sein", "bitte", "klar", "sichtbar",
    }
    seen: set[str] = set()
    words: list[str] = []
    for raw in re.findall(r"[A-Za-z0-9äöüÄÖÜß_-]+", str(text or "")):
        word = raw.strip("_- ")
        if len(word) < 3:
            continue
        key = word.lower()
        if key in stopwords or key in seen:
            continue
        seen.add(key)
        words.append(word)
        if len(words) >= limit:
            break
    return words


def _compact_text(text: str | None, *, max_chars: int = 96) -> str:
    value = " ".join(str(text or "").replace("\n", " ").split())
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _required_proof_text(record: Verification) -> str:
    parts: list[str] = []
    if record.requested_seal_number:
        parts.append(f"Soll: {record.requested_seal_number}")
    if record.verification_criteria:
        keywords = _compact_keywords(record.verification_criteria, limit=4)
        if keywords:
            parts.append(f"Check: {', '.join(keywords)}")
    if not parts:
        parts.append("Allg. Verifikation")
    return _compact_text(" | ".join(parts), max_chars=88)


def _detected_proof_text(status: str, analysis: str | None, observed_seal_number: str | None) -> str:
    parts: list[str] = []
    status_label = {
        "confirmed": "OK",
        "suspicious": "Verdacht",
        "pending": "Offen",
    }.get((status or "").strip().lower(), (status or "Unbekannt").strip() or "Unbekannt")
    parts.append(status_label)
    if observed_seal_number:
        parts.append(f"Ist: {observed_seal_number}")
    if analysis:
        parts.append(analysis.strip())
    return _compact_text(" | ".join(parts), max_chars=110)


@router.post("/{session_id}/verifications/request")
def request_verification(session_id: int, payload: VerificationRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    get_owned_session(request, db, session_id)
    record = Verification(
        session_id=session_id,
        requested_seal_number=payload.requested_seal_number,
        status="pending",
        linked_task_id=payload.linked_task_id,
        verification_criteria=payload.verification_criteria,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"verification_id": record.id, "status": record.status}


@router.post("/{session_id}/verifications/{verification_id}/upload")
async def upload_verification(
    session_id: int,
    verification_id: int,
    file: UploadFile = File(...),
    observed_seal_number: str | None = Form(default=None),
    request: Request = None,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    record = (
        db.query(Verification)
        .filter(Verification.id == verification_id, Verification.session_id == session_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Verification not found")

    target_dir = Path(settings.media_dir) / "verifications" / "chat" / str(session_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / _chat_verification_filename(
        session_id,
        verification_id,
        file.filename,
        linked_task_id=record.linked_task_id,
    )

    data = await file.read()
    status, analysis = analyze_verification(
        image_bytes=data,
        filename=file.filename or "upload.jpg",
        requested_seal_number=record.requested_seal_number,
        observed_seal_number=observed_seal_number,
        verification_criteria=record.verification_criteria,
    )

    stamped = stamp_verification_proof(
        data,
        required_text=_required_proof_text(record),
        detected_text=_detected_proof_text(status, analysis, observed_seal_number),
    )
    target_path.write_bytes(stamped)

    record.image_path = str(target_path)
    record.observed_seal_number = observed_seal_number
    record.status = status
    record.ai_response = analysis

    # Auto-resolve linked task
    if record.linked_task_id:
        task = db.query(Task).filter(Task.id == record.linked_task_id, Task.session_id == session_id).first()
        if task and task.status == "pending":
            now = datetime.now(timezone.utc)
            if status == "confirmed":
                task.status = "completed"
                task.completed_at = now
                content = f"✓ Verifikation bestätigt – Task '{task.title}' abgeschlossen."
                if analysis:
                    content += f" {analysis}"
                db.add(Message(
                    session_id=session_id,
                    role="system",
                    content=content,
                    message_type="task_reward",
                ))
            else:
                task.status = "failed"
                TaskService.apply_task_consequence(db=db, session_obj=session_obj, task=task, now=now)
                content = f"⚠ Verifikation abgelehnt – Task '{task.title}' fehlgeschlagen."
                if analysis:
                    content += f" {analysis}"
                db.add(Message(
                    session_id=session_id,
                    role="system",
                    content=content,
                    message_type="task_failed",
                ))
            db.add(task)
    else:
        # Standalone verification (no linked task) – always write a result message
        status_label = {"confirmed": "✓ bestätigt", "suspicious": "⚠ verdächtig"}.get(status, "⏳ ausstehend")
        content = f"Verifikation {status_label}."
        if analysis:
            content += f" {analysis}"
        db.add(Message(
            session_id=session_id,
            role="system",
            content=content,
            message_type="verification_result",
        ))

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "verification_id": record.id,
        "status": record.status,
        "observed_seal_number": record.observed_seal_number,
        "analysis": record.ai_response,
        "image_url": _verification_image_url(record.image_path),
    }


@router.get("/{session_id}/verifications")
def list_verifications(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    get_owned_session(request, db, session_id)
    rows = (
        db.query(Verification)
        .filter(Verification.session_id == session_id)
        .order_by(Verification.id.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "items": [
            {
                "id": item.id,
                "status": item.status,
                "requested_seal_number": item.requested_seal_number,
                "observed_seal_number": item.observed_seal_number,
                "analysis": item.ai_response,
                "image_url": _verification_image_url(item.image_path),
            }
            for item in rows
        ],
    }
