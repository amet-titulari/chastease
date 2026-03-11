from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.models.message import Message
from app.models.verification import Verification
from app.services.task_service import TaskService
from app.services.verification_analysis import analyze_verification

router = APIRouter(prefix="/api/sessions", tags=["verification"])


class VerificationRequest(BaseModel):
    requested_seal_number: str | None = None
    linked_task_id: int | None = None
    verification_criteria: str | None = None


def _load_session(db: Session, session_id: int) -> SessionModel:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


@router.post("/{session_id}/verifications/request")
def request_verification(session_id: int, payload: VerificationRequest, db: Session = Depends(get_db)) -> dict:
    _load_session(db, session_id)
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
    db: Session = Depends(get_db),
) -> dict:
    _load_session(db, session_id)
    record = (
        db.query(Verification)
        .filter(Verification.id == verification_id, Verification.session_id == session_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Verification not found")

    target_dir = Path(settings.media_dir) / "verifications"
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    target_path = target_dir / f"{uuid4().hex}{suffix}"

    data = await file.read()
    target_path.write_bytes(data)

    record.image_path = str(target_path)
    record.observed_seal_number = observed_seal_number

    status, analysis = analyze_verification(
        image_bytes=data,
        filename=file.filename or "upload.jpg",
        requested_seal_number=record.requested_seal_number,
        observed_seal_number=observed_seal_number,
        verification_criteria=record.verification_criteria,
    )
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
                db.add(Message(
                    session_id=session_id,
                    role="system",
                    content=f"Task '{task.title}' per Foto-Verifikation abgeschlossen.",
                    message_type="task_reward",
                ))
            else:
                task.status = "failed"
                TaskService.apply_task_consequence(db=db, session_obj=_load_session(db, session_id), task=task, now=now)
                db.add(Message(
                    session_id=session_id,
                    role="system",
                    content=f"Task '{task.title}' fehlgeschlagen: Verifikation nicht bestätigt.",
                    message_type="task_failed",
                ))
            db.add(task)

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "verification_id": record.id,
        "status": record.status,
        "observed_seal_number": record.observed_seal_number,
        "analysis": record.ai_response,
    }


@router.get("/{session_id}/verifications")
def list_verifications(session_id: int, db: Session = Depends(get_db)) -> dict:
    _load_session(db, session_id)
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
            }
            for item in rows
        ],
    }
