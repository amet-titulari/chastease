from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.verification import Verification
from app.security import verify_admin_secret

router = APIRouter(prefix="/api/sessions", tags=["verification"])


class VerificationRequest(BaseModel):
    requested_seal_number: str | None = None


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
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"verification_id": record.id, "status": record.status}


@router.post("/{session_id}/verifications/{verification_id}/upload")
async def upload_verification(
    session_id: int,
    verification_id: int,
    _: None = Depends(verify_admin_secret),
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

    if record.requested_seal_number and observed_seal_number and record.requested_seal_number != observed_seal_number:
        record.status = "suspicious"
        record.ai_response = "Plombennummer stimmt nicht ueberein."
    else:
        record.status = "confirmed"
        record.ai_response = "Verifikation eingegangen und markiert."

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
