from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.safety_log import SafetyLog
from app.models.session import Session as SessionModel
from app.security import require_admin_session_user, verify_admin_secret
from app.services.audit_logger import audit_log
from app.services.session_access import get_owned_session

router = APIRouter(prefix="/api/sessions", tags=["safety"])


class TrafficLightRequest(BaseModel):
    color: str = Field(pattern="^(green|yellow|red)$")


class EmergencyReleaseRequest(BaseModel):
    reason: str = Field(min_length=5)


@router.post("/{session_id}/safety/traffic-light")
def traffic_light(
    session_id: int,
    payload: TrafficLightRequest,
    _admin_user = Depends(require_admin_session_user),
    _: None = Depends(verify_admin_secret),
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    if payload.color == "red" and session_obj.status == "active":
        session_obj.status = "paused"

    db.add(SafetyLog(session_id=session_id, event_type=payload.color, reason="traffic_light"))
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    audit_log("safety_traffic_light", session_id=session_id, color=payload.color, status=session_obj.status)
    return {"session_id": session_id, "status": session_obj.status, "color": payload.color}


@router.post("/{session_id}/safety/resume")
def resume_session(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    """Reactivate a safeword-stopped session (e.g. accidental trigger)."""
    session_obj = get_owned_session(request, db, session_id)
    if session_obj.status not in ("safeword_stopped", "yellow", "red"):
        raise HTTPException(status_code=400, detail="Session kann nicht reaktiviert werden.")
    session_obj.status = "active"
    db.add(SafetyLog(session_id=session_id, event_type="resumed", reason="manual_resume"))
    db.add(session_obj)
    db.commit()
    audit_log("safety_resumed", session_id=session_id)
    return {"session_id": session_id, "status": session_obj.status}


@router.post("/{session_id}/safety/safeword")
def safeword(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    session_obj.status = "safeword_stopped"
    db.add(SafetyLog(session_id=session_id, event_type="safeword", reason="immediate_stop"))
    db.add(session_obj)
    db.commit()
    audit_log("safety_safeword", session_id=session_id)
    return {"session_id": session_id, "status": session_obj.status}


@router.post("/{session_id}/safety/emergency-release")
def emergency_release(
    session_id: int,
    payload: EmergencyReleaseRequest,
    _admin_user = Depends(require_admin_session_user),
    _: None = Depends(verify_admin_secret),
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    session_obj.status = "emergency_stopped"
    db.add(SafetyLog(session_id=session_id, event_type="emergency_release", reason=payload.reason))
    db.add(session_obj)
    db.commit()
    audit_log("safety_emergency_release", session_id=session_id, reason=payload.reason)
    return {"session_id": session_id, "status": session_obj.status, "reason": payload.reason}


@router.get("/{session_id}/safety/logs")
def get_safety_logs(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    get_owned_session(request, db, session_id)
    logs = (
        db.query(SafetyLog)
        .filter(SafetyLog.session_id == session_id)
        .order_by(SafetyLog.id.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "logs": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "reason": item.reason,
                "created_at": str(item.created_at),
            }
            for item in logs
        ],
    }
