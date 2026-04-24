"""Admin REST endpoints for the Howl Remote API E-Stim integration."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.otc_settings import OtcSettings
from app.security import require_admin_session_user
from app.services.audit_logger import audit_log
from app.services.howl_client import howl_status, send_howl_pulse

router = APIRouter()
howl_router = APIRouter(prefix="/api/howl", tags=["howl"])
legacy_router = APIRouter(prefix="/api/otc", tags=["otc-legacy"])


class OtcSettingsUpdateRequest(BaseModel):
    enabled: bool = False
    otc_url: str | None = Field(default=None, max_length=512)
    howl_access_key: str | None = Field(default=None, max_length=512)
    channel: str = Field(default="A", max_length=4, pattern="^(A|B|AB)$")
    intensity_continuous: int = Field(default=30, ge=0, le=100)
    intensity_fail: int = Field(default=40, ge=0, le=100)
    intensity_penalty: int = Field(default=70, ge=0, le=100)
    intensity_pass: int = Field(default=20, ge=0, le=100)
    ticks_continuous: int = Field(default=50, ge=0, le=300)
    ticks_fail: int = Field(default=20, ge=0, le=300)
    ticks_penalty: int = Field(default=40, ge=0, le=300)
    ticks_pass: int = Field(default=10, ge=0, le=300)
    pattern_continuous: str = Field(default="RELENTLESS", max_length=120)
    pattern_fail: str = Field(default="RELENTLESS", max_length=120)
    pattern_penalty: str = Field(default="RELENTLESS", max_length=120)
    pattern_pass: str = Field(default="RELENTLESS", max_length=120)


class OtcTestRequest(BaseModel):
    channel: str = Field(default="A", max_length=4, pattern="^(A|B|AB)$")
    intensity: int = Field(default=50, ge=1, le=100)
    ticks: int = Field(default=10, ge=1, le=300)
    pattern: str = Field(default="RELENTLESS", max_length=120)


def _settings_payload(s: OtcSettings | None) -> dict:
    if s is None:
        return {
            "enabled": False,
            "otc_url": None,
            "howl_access_key": None,
            "channel": "A",
            "intensity_continuous": 30,
            "intensity_fail": 40,
            "intensity_penalty": 70,
            "intensity_pass": 20,
            "ticks_continuous": 50,
            "ticks_fail": 20,
            "ticks_penalty": 40,
            "ticks_pass": 10,
            "pattern_continuous": "RELENTLESS",
            "pattern_fail": "RELENTLESS",
            "pattern_penalty": "RELENTLESS",
            "pattern_pass": "RELENTLESS",
            "created_at": None,
            "updated_at": None,
        }
    return {
        "enabled": bool(s.enabled),
        "otc_url": s.otc_url,
        "howl_access_key": s.howl_access_key,
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


@howl_router.get("/settings")
@legacy_router.get("/settings")
def get_otc_settings(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    return _settings_payload(_load(db))


@howl_router.put("/settings")
@legacy_router.put("/settings")
def update_otc_settings(
    payload: OtcSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    row = _load(db)
    if row is None:
        row = OtcSettings(singleton_key="default")

    row.enabled = payload.enabled
    row.otc_url = (payload.otc_url or "").strip() or None
    row.howl_access_key = (payload.howl_access_key or "").strip() or None
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

    audit_log(
        "admin_otc_settings_updated",
        actor_user_id=user.id,
        enabled=row.enabled,
        otc_url=(str(row.otc_url or "").strip() or None),
        howl_access_key_set=bool(str(row.howl_access_key or "").strip()),
        channel=row.channel,
    )
    return _settings_payload(row)


@howl_router.get("/status")
@legacy_router.get("/status")
def get_otc_status(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    row = _load(db)
    if row is None or not row.enabled:
        return {
            "running": False,
            "connected": False,
            "url": None,
            "api": "howl",
            "detail": "disabled",
        }
    base_url = str(row.otc_url or "").strip()
    access_key = str(row.howl_access_key or "").strip()
    return howl_status(base_url, access_key)


@howl_router.post("/test")
@legacy_router.post("/test")
def test_otc_pulse(
    payload: OtcTestRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    row = _load(db)
    if row is None or not row.enabled:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Howl integration is not enabled")
    base_url = str(row.otc_url or "").strip()
    if not base_url:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Howl API URL is not configured")
    access_key = str(row.howl_access_key or "").strip()
    if not access_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Howl access key is not configured")

    ok = send_howl_pulse(
        base_url=base_url,
        access_key=access_key,
        channel=payload.channel,
        intensity=payload.intensity,
        ticks=payload.ticks,
        activity=payload.pattern,
    )
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="Howl test pulse request failed")

    audit_log(
        "admin_otc_test_pulse_sent",
        actor_user_id=user.id,
        channel=payload.channel,
        intensity=payload.intensity,
        ticks=payload.ticks,
    )
    return {"queued": True, "channel": payload.channel}


router.include_router(howl_router)
router.include_router(legacy_router)
