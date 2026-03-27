from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.player_profile import PlayerProfile
from app.services.lovense import (
    LovenseConfigError,
    LovenseGatewayError,
    lovense_status_payload,
    request_lovense_auth_token,
)
from app.services.lovense_policy import get_lovense_policy_for_profile, save_lovense_policy_for_profile
from app.services.session_access import get_owned_session, require_session_user

router = APIRouter(prefix="/api/lovense", tags=["lovense"])


class LovensePolicyUpdateRequest(BaseModel):
    min_intensity: int | None = None
    max_intensity: int | None = None
    min_step_duration_seconds: int | None = None
    max_step_duration_seconds: int | None = None
    min_pause_seconds: int | None = None
    max_pause_seconds: int | None = None
    max_plan_duration_seconds: int | None = None
    max_plan_steps: int | None = None
    allow_presets: bool | None = None
    allow_append_mode: bool | None = None
    allowed_commands: dict[str, Any] | None = None


@router.get("/sessions/{session_id}/status")
def lovense_session_status(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    user = require_session_user(request, db)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    payload = lovense_status_payload()
    payload["session_id"] = session_id
    payload["player_name"] = (player.nickname if player and player.nickname else user.username)
    return payload


@router.post("/sessions/{session_id}/bootstrap")
def lovense_session_bootstrap(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    user = require_session_user(request, db)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    try:
        payload = request_lovense_auth_token(user=user, player=player)
    except LovenseConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LovenseGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "session_id": session_id,
        **payload,
    }


@router.get("/sessions/{session_id}/policy")
def lovense_session_policy(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    return {
        "session_id": session_id,
        "policy": get_lovense_policy_for_profile(player),
    }


@router.post("/sessions/{session_id}/policy")
def update_lovense_session_policy(
    session_id: int,
    payload: LovensePolicyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if player is None:
        raise HTTPException(status_code=404, detail="Player profile not found")
    try:
        policy = save_lovense_policy_for_profile(player, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.add(player)
    db.commit()
    return {
        "session_id": session_id,
        "policy": policy,
    }
