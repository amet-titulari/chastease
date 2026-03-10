import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contract import Contract, ContractAddendum
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.models.seal_history import SealHistory
from app.models.session import Session as SessionModel
from app.services.contract_service import build_contract_text
from app.services.session_service import SessionService
from app.security import verify_admin_secret

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    persona_name: str = Field(min_length=1, max_length=120)
    player_nickname: str = Field(min_length=1, max_length=120)
    min_duration_seconds: int = Field(ge=60)
    max_duration_seconds: int | None = Field(default=None, ge=60)


class ProposeAddendumRequest(BaseModel):
    change_description: str = Field(min_length=3)
    proposed_changes: dict = Field(default_factory=dict)


class AddendumConsentRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


def _ensure_ws_auth_token(session_obj: SessionModel) -> None:
    if session_obj.ws_auth_token:
        return
    session_obj.ws_auth_token = secrets.token_urlsafe(24)
    session_obj.ws_auth_token_created_at = datetime.now(timezone.utc)


def _rotate_ws_auth_token(session_obj: SessionModel) -> None:
    session_obj.ws_auth_token = secrets.token_urlsafe(24)
    session_obj.ws_auth_token_created_at = datetime.now(timezone.utc)


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
    return {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "min_duration_seconds": session_obj.min_duration_seconds,
        "max_duration_seconds": session_obj.max_duration_seconds,
        "lock_start": str(session_obj.lock_start) if session_obj.lock_start else None,
        "lock_end": str(session_obj.lock_end) if session_obj.lock_end else None,
        "ws_auth_token": session_obj.ws_auth_token,
        "contract_signed": bool(contract and contract.signed_at),
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
