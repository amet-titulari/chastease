import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contract import Contract, ContractAddendum
from app.models.hygiene_opening import HygieneOpening
from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.safety_log import SafetyLog
from app.models.seal_history import SealHistory
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.models.verification import Verification
from app.services.contract_service import build_contract_text
from app.services.session_service import SessionService
from app.security import verify_admin_secret

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    persona_name: str = Field(min_length=1, max_length=120)
    player_nickname: str = Field(min_length=1, max_length=120)
    min_duration_seconds: int = Field(ge=60)
    max_duration_seconds: int | None = Field(default=None, ge=60)
    hygiene_limit_daily: int | None = Field(default=None, ge=0)
    hygiene_limit_weekly: int | None = Field(default=None, ge=0)
    hygiene_limit_monthly: int | None = Field(default=None, ge=0)


class ProposeAddendumRequest(BaseModel):
    change_description: str = Field(min_length=3)
    proposed_changes: dict = Field(default_factory=dict)


class AddendumConsentRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


class TimerAdjustRequest(BaseModel):
    seconds: int = Field(ge=1)


class UpdatePlayerProfileRequest(BaseModel):
    experience_level: str | None = Field(default=None, min_length=1, max_length=50)
    preferences: dict | None = None
    soft_limits: list[str] | None = None
    hard_limits: list[str] | None = None
    reaction_patterns: dict | None = None
    needs: dict | None = None


def _ensure_ws_auth_token(session_obj: SessionModel) -> None:
    if session_obj.ws_auth_token:
        return
    session_obj.ws_auth_token = secrets.token_urlsafe(24)
    session_obj.ws_auth_token_created_at = datetime.now(timezone.utc)


def _rotate_ws_auth_token(session_obj: SessionModel) -> None:
    session_obj.ws_auth_token = secrets.token_urlsafe(24)
    session_obj.ws_auth_token_created_at = datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _remaining_seconds(session_obj: SessionModel, now: datetime) -> int:
    if session_obj.lock_end is None:
        return 0
    anchor = now
    if session_obj.timer_frozen and session_obj.freeze_start is not None:
        anchor = _as_utc(session_obj.freeze_start)
    return max(0, int((_as_utc(session_obj.lock_end) - anchor).total_seconds()))


@router.get("/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not session_obj.ws_auth_token:
        _ensure_ws_auth_token(session_obj)
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()

    return {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "min_duration_seconds": session_obj.min_duration_seconds,
        "max_duration_seconds": session_obj.max_duration_seconds,
        "hygiene_limit_daily": session_obj.hygiene_limit_daily,
        "hygiene_limit_weekly": session_obj.hygiene_limit_weekly,
        "hygiene_limit_monthly": session_obj.hygiene_limit_monthly,
        "lock_start": str(session_obj.lock_start) if session_obj.lock_start else None,
        "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
        "ws_auth_token": session_obj.ws_auth_token,
        "contract_signed": bool(contract and contract.signed_at),
        "player_profile": {
            "id": profile.id,
            "experience_level": profile.experience_level,
            "preferences": json.loads(profile.preferences_json),
            "soft_limits": json.loads(profile.soft_limits_json),
            "hard_limits": json.loads(profile.hard_limits_json),
            "reaction_patterns": json.loads(profile.reaction_patterns_json),
            "needs": json.loads(profile.needs_json),
        }
        if profile
        else None,
    }


@router.put("/{session_id}/player-profile")
def update_player_profile(
    session_id: int,
    payload: UpdatePlayerProfileRequest,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Player profile not found")

    if payload.experience_level is not None:
        profile.experience_level = payload.experience_level
    if payload.preferences is not None:
        profile.preferences_json = json.dumps(payload.preferences)
    if payload.soft_limits is not None:
        profile.soft_limits_json = json.dumps(payload.soft_limits)
    if payload.hard_limits is not None:
        profile.hard_limits_json = json.dumps(payload.hard_limits)
    if payload.reaction_patterns is not None:
        profile.reaction_patterns_json = json.dumps(payload.reaction_patterns)
    if payload.needs is not None:
        profile.needs_json = json.dumps(payload.needs)

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {
        "session_id": session_id,
        "player_profile": {
            "id": profile.id,
            "experience_level": profile.experience_level,
            "preferences": json.loads(profile.preferences_json),
            "soft_limits": json.loads(profile.soft_limits_json),
            "hard_limits": json.loads(profile.hard_limits_json),
            "reaction_patterns": json.loads(profile.reaction_patterns_json),
            "needs": json.loads(profile.needs_json),
        },
    }


@router.get("/{session_id}/seal-history")
def get_seal_history(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    entries = (
        db.query(SealHistory)
        .filter(SealHistory.session_id == session_id)
        .order_by(SealHistory.id.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "entries": [
            {
                "id": entry.id,
                "seal_number": entry.seal_number,
                "status": entry.status,
                "note": entry.note,
                "applied_at": str(entry.applied_at),
            }
            for entry in entries
        ],
    }


def _collect_session_events(db: Session, session_id: int) -> list[tuple[datetime, dict]]:
    events: list[tuple[datetime, dict]] = []

    message_rows = db.query(Message).filter(Message.session_id == session_id).all()
    for row in message_rows:
        occurred_at = _as_utc(row.created_at)
        events.append(
            (
                occurred_at,
                {
                    "source": "message",
                    "event_type": row.message_type,
                    "occurred_at": str(row.created_at),
                    "data": {
                        "id": row.id,
                        "role": row.role,
                        "content": row.content,
                    },
                },
            )
        )

    safety_rows = db.query(SafetyLog).filter(SafetyLog.session_id == session_id).all()
    for row in safety_rows:
        occurred_at = _as_utc(row.created_at)
        events.append(
            (
                occurred_at,
                {
                    "source": "safety",
                    "event_type": row.event_type,
                    "occurred_at": str(row.created_at),
                    "data": {
                        "id": row.id,
                        "reason": row.reason,
                    },
                },
            )
        )

    hygiene_rows = db.query(HygieneOpening).filter(HygieneOpening.session_id == session_id).all()
    for row in hygiene_rows:
        ts = row.opened_at or row.requested_at or datetime.now(timezone.utc)
        occurred_at = _as_utc(ts)
        events.append(
            (
                occurred_at,
                {
                    "source": "hygiene",
                    "event_type": row.status,
                    "occurred_at": str(ts),
                    "data": {
                        "id": row.id,
                        "overrun_seconds": row.overrun_seconds,
                        "penalty_seconds": row.penalty_seconds,
                    },
                },
            )
        )

    task_rows = db.query(Task).filter(Task.session_id == session_id).all()
    for row in task_rows:
        ts = row.completed_at or row.consequence_applied_at or row.created_at or datetime.now(timezone.utc)
        occurred_at = _as_utc(ts)
        events.append(
            (
                occurred_at,
                {
                    "source": "task",
                    "event_type": row.status,
                    "occurred_at": str(ts),
                    "data": {
                        "id": row.id,
                        "title": row.title,
                        "consequence_applied_seconds": row.consequence_applied_seconds,
                    },
                },
            )
        )

    verification_rows = db.query(Verification).filter(Verification.session_id == session_id).all()
    for row in verification_rows:
        ts = row.created_at or row.requested_at or datetime.now(timezone.utc)
        occurred_at = _as_utc(ts)
        events.append(
            (
                occurred_at,
                {
                    "source": "verification",
                    "event_type": row.status,
                    "occurred_at": str(ts),
                    "data": {
                        "id": row.id,
                        "requested_seal_number": row.requested_seal_number,
                        "observed_seal_number": row.observed_seal_number,
                    },
                },
            )
        )

    events.sort(key=lambda item: item[0])
    return events


@router.get("/{session_id}/events")
def get_session_events(
    session_id: int,
    source: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    events = [item for _, item in _collect_session_events(db, session_id)]
    if source:
        events = [item for item in events if item["source"] == source]
    if event_type:
        events = [item for item in events if item["event_type"] == event_type]
    events = events[:limit]

    return {
        "session_id": session_id,
        "session_status": session_obj.status,
        "items": events,
    }


@router.get("/{session_id}/events/export")
def export_session_events(
    session_id: int,
    format: str = Query(default="text", pattern="^(text|json)$"),
    source: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    payload = get_session_events(
        session_id=session_id,
        source=source,
        event_type=event_type,
        limit=limit,
        db=db,
    )
    if format == "json":
        return payload

    lines = [f"session_id={payload['session_id']} status={payload['session_status']}"]
    for item in payload["items"]:
        lines.append(
            f"{item['occurred_at']} | source={item['source']} | type={item['event_type']} | data={json.dumps(item['data'])}"
        )
    return PlainTextResponse("\n".join(lines))


@router.get("/{session_id}/contract")
def get_contract(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    addenda = (
        db.query(ContractAddendum)
        .filter(ContractAddendum.contract_id == contract.id)
        .order_by(ContractAddendum.id.asc())
        .all()
    )

    return {
        "session_id": session_id,
        "contract": {
            "id": contract.id,
            "content_text": contract.content_text,
            "signed_at": str(contract.signed_at) if contract.signed_at else None,
            "parameters_snapshot": contract.parameters_snapshot,
            "created_at": str(contract.created_at),
        },
        "addenda": [
            {
                "id": item.id,
                "change_description": item.change_description,
                "proposed_changes": json.loads(item.proposed_changes_json),
                "proposed_by": item.proposed_by,
                "player_consent": item.player_consent,
                "player_consent_at": str(item.player_consent_at) if item.player_consent_at else None,
                "created_at": str(item.created_at),
            }
            for item in addenda
        ],
    }


@router.get("/{session_id}/contract/export")
def export_contract(
    session_id: int,
    format: str = Query(default="text", pattern="^(text|json)$"),
    db: Session = Depends(get_db),
):
    payload = get_contract(session_id=session_id, db=db)
    if format == "json":
        return payload

    contract = payload["contract"]
    lines = [
        f"session_id={payload['session_id']}",
        f"contract_id={contract['id']}",
        f"signed_at={contract['signed_at']}",
        "",
        "CONTENT:",
        contract["content_text"],
        "",
        "ADDENDA:",
    ]
    for item in payload["addenda"]:
        lines.append(
            f"- #{item['id']} consent={item['player_consent']} desc={item['change_description']} changes={json.dumps(item['proposed_changes'])}"
        )

    return PlainTextResponse("\n".join(lines))


@router.post("")
def create_session(payload: CreateSessionRequest, db: Session = Depends(get_db)) -> dict:
    persona = Persona(name=payload.persona_name)
    player = PlayerProfile(nickname=payload.player_nickname)
    db.add_all([persona, player])
    db.flush()

    session_obj = SessionModel(
        persona_id=persona.id,
        player_profile_id=player.id,
        min_duration_seconds=payload.min_duration_seconds,
        max_duration_seconds=payload.max_duration_seconds,
        hygiene_limit_daily=payload.hygiene_limit_daily,
        hygiene_limit_weekly=payload.hygiene_limit_weekly,
        hygiene_limit_monthly=payload.hygiene_limit_monthly,
        status="draft",
    )
    _ensure_ws_auth_token(session_obj)
    db.add(session_obj)
    db.flush()

    contract = Contract(
        session_id=session_obj.id,
        content_text=build_contract_text(
            persona_name=persona.name,
            player_nickname=player.nickname,
            min_duration_seconds=session_obj.min_duration_seconds,
            max_duration_seconds=session_obj.max_duration_seconds,
        ),
        parameters_snapshot="{}",
    )
    db.add(contract)
    db.commit()
    db.refresh(session_obj)

    return {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "ws_auth_token": session_obj.ws_auth_token,
        "contract_required": True,
        "contract_preview": contract.content_text,
    }


@router.post("/{session_id}/sign-contract")
def sign_contract(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.signed_at:
        if not session_obj.ws_auth_token:
            _ensure_ws_auth_token(session_obj)
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)
        return {
            "session_id": session_id,
            "status": session_obj.status,
            "ws_auth_token": session_obj.ws_auth_token,
            "already_signed": True,
        }

    updated = SessionService.sign_contract_and_start(db=db, session_obj=session_obj, contract_obj=contract)
    _ensure_ws_auth_token(updated)
    db.add(updated)
    db.commit()
    db.refresh(updated)
    return {
        "session_id": updated.id,
        "status": updated.status,
        "lock_end": str(updated.lock_end),
        "ws_auth_token": updated.ws_auth_token,
    }


@router.post("/{session_id}/chat/ws-token/rotate")
def rotate_chat_ws_token(
    session_id: int,
    _: None = Depends(verify_admin_secret),
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    _rotate_ws_auth_token(session_obj)
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return {
        "session_id": session_obj.id,
        "ws_auth_token": session_obj.ws_auth_token,
        "rotated_at": str(session_obj.ws_auth_token_created_at),
    }


@router.get("/{session_id}/timer")
def get_timer_state(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc)
    return {
        "session_id": session_id,
        "status": session_obj.status,
        "timer_frozen": session_obj.timer_frozen,
        "remaining_seconds": _remaining_seconds(session_obj, now),
        "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
    }


@router.post("/{session_id}/timer/add")
def add_timer_time(session_id: int, payload: TimerAdjustRequest, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    session_obj.lock_end = _as_utc(session_obj.lock_end) + timedelta(seconds=payload.seconds)
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    return {
        "session_id": session_id,
        "lock_end": str(session_obj.lock_end),
        "remaining_seconds": _remaining_seconds(session_obj, datetime.now(timezone.utc)),
    }


@router.post("/{session_id}/timer/remove")
def remove_timer_time(session_id: int, payload: TimerAdjustRequest, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    now = datetime.now(timezone.utc)
    floor = _as_utc(session_obj.freeze_start) if session_obj.timer_frozen and session_obj.freeze_start else now
    session_obj.lock_end = max(floor, _as_utc(session_obj.lock_end) - timedelta(seconds=payload.seconds))
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    return {
        "session_id": session_id,
        "lock_end": str(session_obj.lock_end),
        "remaining_seconds": _remaining_seconds(session_obj, now),
    }


@router.post("/{session_id}/timer/freeze")
def freeze_timer(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    if not session_obj.timer_frozen:
        session_obj.timer_frozen = True
        session_obj.freeze_start = datetime.now(timezone.utc)
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)

    return {
        "session_id": session_id,
        "timer_frozen": session_obj.timer_frozen,
        "freeze_start": str(session_obj.freeze_start) if session_obj.freeze_start else None,
    }


@router.post("/{session_id}/timer/unfreeze")
def unfreeze_timer(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_obj.lock_end is None:
        raise HTTPException(status_code=400, detail="Session timer not initialized")

    now = datetime.now(timezone.utc)
    if session_obj.timer_frozen and session_obj.freeze_start is not None:
        frozen_for = now - _as_utc(session_obj.freeze_start)
        session_obj.lock_end = _as_utc(session_obj.lock_end) + frozen_for
        session_obj.timer_frozen = False
        session_obj.freeze_start = None
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)

    return {
        "session_id": session_id,
        "timer_frozen": session_obj.timer_frozen,
        "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
        "remaining_seconds": _remaining_seconds(session_obj, now),
    }


@router.post("/{session_id}/contract/addenda")
def propose_contract_addendum(
    session_id: int,
    payload: ProposeAddendumRequest,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.signed_at:
        raise HTTPException(status_code=400, detail="Contract must be signed before addenda")

    addendum = ContractAddendum(
        contract_id=contract.id,
        proposed_changes_json=json.dumps(payload.proposed_changes),
        change_description=payload.change_description,
        proposed_by="ai",
        player_consent="pending",
    )
    db.add(addendum)
    db.commit()
    db.refresh(addendum)

    return {
        "addendum_id": addendum.id,
        "session_id": session_id,
        "status": addendum.player_consent,
    }


@router.post("/{session_id}/contract/addenda/{addendum_id}/consent")
def consent_contract_addendum(
    session_id: int,
    addendum_id: int,
    payload: AddendumConsentRequest,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    contract = db.query(Contract).filter(Contract.session_id == session_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    addendum = (
        db.query(ContractAddendum)
        .filter(ContractAddendum.id == addendum_id, ContractAddendum.contract_id == contract.id)
        .first()
    )
    if not addendum:
        raise HTTPException(status_code=404, detail="Addendum not found")
    if addendum.player_consent != "pending":
        return {
            "addendum_id": addendum.id,
            "decision": addendum.player_consent,
            "session_id": session_id,
            "already_decided": True,
        }

    addendum.player_consent = payload.decision
    addendum.player_consent_at = datetime.now(timezone.utc)

    if payload.decision == "approved":
        proposed_changes = json.loads(addendum.proposed_changes_json)
        # Only allow non-safety session parameter changes in this initial implementation.
        allowed_keys = {"min_duration_seconds", "max_duration_seconds"}
        for key, value in proposed_changes.items():
            if key not in allowed_keys:
                continue
            setattr(session_obj, key, value)

        if session_obj.status == "active" and session_obj.lock_start is not None:
            session_obj.lock_end = session_obj.lock_start + timedelta(seconds=session_obj.min_duration_seconds)

        db.add(session_obj)

    db.add(addendum)
    db.commit()
    db.refresh(addendum)

    return {
        "addendum_id": addendum.id,
        "session_id": session_id,
        "decision": addendum.player_consent,
        "consented_at": str(addendum.player_consent_at) if addendum.player_consent_at else None,
    }
