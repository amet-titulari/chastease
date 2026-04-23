"""Admin REST endpoints for the OTC (open-DGLAB-controller) E-Stim integration."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.otc_settings import OtcSettings
from app.security import require_admin_session_user
from app.services.audit_logger import audit_log
from app.services.otc_client import otc_status, send_otc_command, start_otc_client, stop_otc_client

router = APIRouter(prefix="/api/otc", tags=["otc"])


class OtcSettingsUpdateRequest(BaseModel):
    enabled: bool = False
    otc_url: str | None = Field(default=None, max_length=512)
    channel: str = Field(default="A", max_length=4, pattern="^(A|B|AB)$")
    intensity_continuous: int = Field(default=30, ge=0, le=100)
    intensity_fail: int = Field(default=40, ge=0, le=100)
    intensity_penalty: int = Field(default=70, ge=0, le=100)
    intensity_pass: int = Field(default=20, ge=0, le=100)
    ticks_continuous: int = Field(default=50, ge=0, le=300)
    ticks_fail: int = Field(default=20, ge=0, le=300)
    ticks_penalty: int = Field(default=40, ge=0, le=300)
    ticks_pass: int = Field(default=10, ge=0, le=300)
    pattern_continuous: str = Field(default="经典", max_length=120)
    pattern_fail: str = Field(default="经典", max_length=120)
    pattern_penalty: str = Field(default="经典", max_length=120)
    pattern_pass: str = Field(default="经典", max_length=120)


class OtcTestRequest(BaseModel):
    channel: str = Field(default="A", max_length=4, pattern="^(A|B|AB)$")
    intensity: int = Field(default=50, ge=1, le=100)
    ticks: int = Field(default=10, ge=1, le=300)
    pattern: str = Field(default="经典", max_length=120)


def _settings_payload(s: OtcSettings | None) -> dict:
    if s is None:
        return {
            "enabled": False,
            "otc_url": None,
            "channel": "A",
            "intensity_continuous": 30,
            "intensity_fail": 40,
            "intensity_penalty": 70,
            "intensity_pass": 20,
            "ticks_continuous": 50,
            "ticks_fail": 20,
            "ticks_penalty": 40,
            "ticks_pass": 10,
            "pattern_continuous": "经典",
            "pattern_fail": "经典",
            "pattern_penalty": "经典",
            "pattern_pass": "经典",
            "created_at": None,
            "updated_at": None,
        }
    return {
        "enabled": bool(s.enabled),
        "otc_url": s.otc_url,
        "channel": s.channel,
        "intensity_continuous": s.intensity_continuous,
        "intensity_fail": s.intensity_fail,
        "intensity_penalty": s.intensity_penalty,
        "intensity_pass": s.intensity_pass,
        "ticks_continuous": s.ticks_continuous,
        "ticks_fail": s.ticks_fail,
        "ticks_penalty": s.ticks_penalty,
        "ticks_pass": s.ticks_pass,
        "pattern_continuous": s.pattern_continuous,
        "pattern_fail": s.pattern_fail,
        "pattern_penalty": s.pattern_penalty,
        "pattern_pass": s.pattern_pass,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _load(db: Session) -> OtcSettings | None:
    return db.query(OtcSettings).filter(OtcSettings.singleton_key == "default").first()


@router.get("/settings")
def get_otc_settings(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    return _settings_payload(_load(db))


@router.put("/settings")
def update_otc_settings(
    payload: OtcSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    row = _load(db)
    if row is None:
        row = OtcSettings(singleton_key="default")

    prev_url = str(row.otc_url or "").strip()
    prev_enabled = bool(row.enabled)

    row.enabled = payload.enabled
    row.otc_url = (payload.otc_url or "").strip() or None
    row.channel = payload.channel
    row.intensity_continuous = payload.intensity_continuous
    row.intensity_fail = payload.intensity_fail
    row.intensity_penalty = payload.intensity_penalty
    row.intensity_pass = payload.intensity_pass
    row.ticks_continuous = payload.ticks_continuous
    row.ticks_fail = payload.ticks_fail
    row.ticks_penalty = payload.ticks_penalty
    row.ticks_pass = payload.ticks_pass
    row.pattern_continuous = payload.pattern_continuous
    row.pattern_fail = payload.pattern_fail
    row.pattern_penalty = payload.pattern_penalty
    row.pattern_pass = payload.pattern_pass

    db.add(row)
    db.commit()
    db.refresh(row)

    new_url = str(row.otc_url or "").strip()
    url_changed = new_url != prev_url

    # Restart / stop the client as needed.
    if row.enabled and new_url:
        if url_changed or not prev_enabled:
            start_otc_client(new_url)
    else:
        if prev_enabled:
            stop_otc_client()

    audit_log(
        "admin_otc_settings_updated",
        actor_user_id=user.id,
        enabled=row.enabled,
        otc_url=new_url or None,
        channel=row.channel,
    )
    return _settings_payload(row)


@router.get("/status")
def get_otc_status(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    return otc_status()


@router.post("/test")
def test_otc_pulse(
    payload: OtcTestRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    row = _load(db)
    if row is None or not row.enabled:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="OTC is not enabled")
    url = str(row.otc_url or "").strip()
    if not url:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="OTC URL is not configured")

    channels = ["A", "B"] if payload.channel == "AB" else [payload.channel]
    for ch in channels:
        send_otc_command({
            "cmd": "set_pattern",
            "channel": ch,
            "pattern_name": payload.pattern,
            "intensity": payload.intensity,
            "ticks": payload.ticks,
        })

    audit_log(
        "admin_otc_test_pulse_sent",
        actor_user_id=user.id,
        channel=payload.channel,
        intensity=payload.intensity,
        ticks=payload.ticks,
    )
    return {"queued": True, "channels": channels}
