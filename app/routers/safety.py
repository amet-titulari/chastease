from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.safety_log import SafetyLog
from app.models.session import Session as SessionModel

router = APIRouter(prefix="/api/sessions", tags=["safety"])


class TrafficLightRequest(BaseModel):
    color: str = Field(pattern="^(green|yellow|red)$")


class EmergencyReleaseRequest(BaseModel):
    reason: str = Field(min_length=5)


def _load_session(db: Session, session_id: int) -> SessionModel:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


@router.post("/{session_id}/safety/traffic-light")
def traffic_light(session_id: int, payload: TrafficLightRequest, db: Session = Depends(get_db)) -> dict:
    session_obj = _load_session(db, session_id)

    if payload.color == "red" and session_obj.status == "active":
        session_obj.status = "paused"

    db.add(SafetyLog(session_id=session_id, event_type=payload.color, reason="traffic_light"))
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    return {"session_id": session_id, "status": session_obj.status, "color": payload.color}


@router.post("/{session_id}/safety/safeword")
def safeword(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = _load_session(db, session_id)
    session_obj.status = "safeword_stopped"
    db.add(SafetyLog(session_id=session_id, event_type="safeword", reason="immediate_stop"))
    db.add(session_obj)
    db.commit()
    return {"session_id": session_id, "status": session_obj.status}


@router.post("/{session_id}/safety/emergency-release")
def emergency_release(
    session_id: int,
    payload: EmergencyReleaseRequest,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = _load_session(db, session_id)
    session_obj.status = "emergency_stopped"
    db.add(SafetyLog(session_id=session_id, event_type="emergency_release", reason=payload.reason))
    db.add(session_obj)
    db.commit()
    return {"session_id": session_id, "status": session_obj.status, "reason": payload.reason}


@router.get("/{session_id}/safety/logs")
def get_safety_logs(session_id: int, db: Session = Depends(get_db)) -> dict:
    _load_session(db, session_id)
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
