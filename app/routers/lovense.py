from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.player_profile import PlayerProfile
from app.services.lovense import (
    LovenseConfigError,
    LovenseGatewayError,
    lovense_status_payload,
    request_lovense_auth_token,
)
from app.services.session_access import get_owned_session, require_session_user

router = APIRouter(prefix="/api/lovense", tags=["lovense"])


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
