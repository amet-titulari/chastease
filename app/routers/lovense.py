from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message
from app.models.persona import Persona
from app.models.player_profile import PlayerProfile
from app.services.lovense import (
    LovenseConfigError,
    LovenseGatewayError,
    lovense_status_payload,
    request_lovense_auth_token,
)
from app.services.lovense_policy import get_lovense_policy_for_profile, save_lovense_policy_for_profile
from app.services.audit_logger import audit_log
from app.services.toy_presets import (
    build_toy_preset_library,
    delete_persona_toy_preset,
    delete_player_toy_preset,
    get_persona_toy_presets,
    get_player_toy_presets,
    save_persona_toy_preset,
    save_player_toy_preset,
)
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


class ToyPresetUpsertRequest(BaseModel):
    key: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    command: str = Field(default="pattern", max_length=20)
    preset: str | None = Field(default=None, max_length=80)
    pattern: str | None = Field(default=None, max_length=240)
    intensity: int | None = None
    duration_seconds: int | None = None
    pause_seconds: int | None = None
    loops: int | None = None
    interval: int | None = None


class LovenseEventRequest(BaseModel):
    source: str = Field(default="manual", max_length=40)
    phase: str = Field(default="executed", max_length=40)
    command: str = Field(min_length=1, max_length=40)
    preset: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    detail: str | None = Field(default=None, max_length=500)
    intensity: int | None = None
    duration_seconds: int | None = None
    pause_seconds: int | None = None
    loops: int | None = None
    toy_id: str | None = Field(default=None, max_length=160)


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


@router.get("/sessions/{session_id}/preset-library")
def lovense_preset_library(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    return {
        "session_id": session_id,
        "library": build_toy_preset_library(profile=player, persona=persona),
    }


@router.get("/sessions/{session_id}/presets")
def lovense_session_presets(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    return {"session_id": session_id, "items": get_player_toy_presets(player)}


@router.post("/sessions/{session_id}/presets")
def upsert_lovense_session_preset(
    session_id: int,
    payload: ToyPresetUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if player is None:
        raise HTTPException(status_code=404, detail="Player profile not found")
    try:
        items = save_player_toy_preset(player, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.add(player)
    db.commit()
    return {"session_id": session_id, "items": items}


@router.delete("/sessions/{session_id}/presets/{preset_key}")
def remove_lovense_session_preset(session_id: int, preset_key: str, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
    if player is None:
        raise HTTPException(status_code=404, detail="Player profile not found")
    items = delete_player_toy_preset(player, preset_key)
    db.add(player)
    db.commit()
    return {"session_id": session_id, "items": items}


@router.get("/sessions/{session_id}/persona-presets")
def lovense_persona_presets(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"session_id": session_id, "persona_id": persona.id, "items": get_persona_toy_presets(persona)}


@router.post("/sessions/{session_id}/persona-presets")
def upsert_lovense_persona_preset(
    session_id: int,
    payload: ToyPresetUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    try:
        items = save_persona_toy_preset(persona, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.add(persona)
    db.commit()
    return {"session_id": session_id, "persona_id": persona.id, "items": items}


@router.delete("/sessions/{session_id}/persona-presets/{preset_key}")
def remove_lovense_persona_preset(session_id: int, preset_key: str, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    persona = db.query(Persona).filter(Persona.id == session_obj.persona_id).first()
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    items = delete_persona_toy_preset(persona, preset_key)
    db.add(persona)
    db.commit()
    return {"session_id": session_id, "persona_id": persona.id, "items": items}


@router.post("/sessions/{session_id}/events")
def log_lovense_event(
    session_id: int,
    payload: LovenseEventRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    get_owned_session(request, db, session_id)
    summary = str(payload.title or payload.command).strip()
    if payload.preset:
        summary = f"{summary} ({payload.preset})"
    if payload.detail:
        summary = f"{summary}: {payload.detail}"
    db.add(
        Message(
            session_id=session_id,
            role="system",
            content=f"Toy {payload.phase}: {summary}",
            message_type="session_event",
        )
    )
    db.commit()
    audit_log("lovense_event", session_id=session_id, **payload.model_dump())
    return {"ok": True, "session_id": session_id}
