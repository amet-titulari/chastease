"""Admin REST endpoints for Lovense game-event feedback configuration.

Settings are stored in PlayerProfile.preferences_json["lovense_game"].
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import require_admin_session_user
from app.services.lovense_estim import default_lovense_game_settings, normalize_lovense_game_settings
from app.services.lovense import lovense_status_payload, send_lovense_server_command, build_lovense_user_payload
from app.models.auth_user import AuthUser
from app.models.player_profile import PlayerProfile

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/lovense-game", tags=["lovense-game"])


def _load_json_dict(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _resolve_player(user: AuthUser, db: Session) -> PlayerProfile | None:
    if user.default_player_profile_id:
        profile = db.query(PlayerProfile).filter(PlayerProfile.id == user.default_player_profile_id).first()
        if profile:
            return profile
    return db.query(PlayerProfile).filter(PlayerProfile.auth_user_id == user.id).first()


class LovenseGameSettingsRequest(BaseModel):
    enabled: bool = False
    intensity_continuous: int = Field(default=6,  ge=0, le=20)
    duration_continuous:  int = Field(default=0,  ge=0, le=300)
    intensity_fail:       int = Field(default=18, ge=0, le=20)
    duration_fail:        int = Field(default=3,  ge=0, le=300)
    intensity_penalty:    int = Field(default=20, ge=0, le=20)
    duration_penalty:     int = Field(default=5,  ge=0, le=300)
    intensity_pass:       int = Field(default=8,  ge=0, le=20)
    duration_pass:        int = Field(default=2,  ge=0, le=300)


class LovenseGameTestRequest(BaseModel):
    intensity: int = Field(default=12, ge=1, le=20)
    duration:  int = Field(default=2,  ge=1, le=30)


@router.get("/settings")
def get_lovense_game_settings(
    user: AuthUser = Depends(require_admin_session_user),
    db: Session = Depends(get_db),
):
    player = _resolve_player(user, db)
    if not player:
        return default_lovense_game_settings()
    prefs = _load_json_dict(player.preferences_json)
    return normalize_lovense_game_settings(prefs.get("lovense_game") or {})


@router.put("/settings")
def put_lovense_game_settings(
    body: LovenseGameSettingsRequest,
    user: AuthUser = Depends(require_admin_session_user),
    db: Session = Depends(get_db),
):
    player = _resolve_player(user, db)
    if not player:
        raise HTTPException(status_code=404, detail="Kein Spielerprofil gefunden.")
    prefs = _load_json_dict(player.preferences_json)
    prefs["lovense_game"] = {
        "enabled":              body.enabled,
        "intensity_continuous": body.intensity_continuous,
        "duration_continuous":  body.duration_continuous,
        "intensity_fail":       body.intensity_fail,
        "duration_fail":        body.duration_fail,
        "intensity_penalty":    body.intensity_penalty,
        "duration_penalty":     body.duration_penalty,
        "intensity_pass":       body.intensity_pass,
        "duration_pass":        body.duration_pass,
    }
    player.preferences_json = json.dumps(prefs)
    db.commit()
    return {"ok": True, "settings": prefs["lovense_game"]}


@router.post("/test")
def test_lovense_game(
    body: LovenseGameTestRequest,
    user: AuthUser = Depends(require_admin_session_user),
    db: Session = Depends(get_db),
):
    status = lovense_status_payload()
    if not status.get("enabled"):
        return {"ok": False, "error": "Lovense ist nicht aktiviert."}

    player = _resolve_player(user, db)
    if not player:
        return {"ok": False, "error": "Kein Spielerprofil gefunden."}

    uid = build_lovense_user_payload(user, player)["uid"]
    action = f"Vibrate:{body.intensity}"
    sent = send_lovense_server_command(uid, action, body.duration)
    if sent:
        return {"ok": True, "uid": uid, "action": action, "duration": body.duration}
    return {"ok": False, "error": "Lovense-Toy nicht erreichbar (Gerät verbunden und Connect-App aktiv?)."}
