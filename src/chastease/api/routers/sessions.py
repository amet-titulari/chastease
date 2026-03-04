import asyncio
import json
import logging
import math
import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, func, select

from chastease.api.runtime import (
    find_or_create_draft_setup_session,
    find_setup_session_id_for_active_session,
    get_db_session,
    iso_utc,
    resolve_user_id_from_token,
    serialize_chastity_session,
)
from chastease.api.schemas import SetupIntegrationsUpdateRequest
from chastease.api.routers.chaster import fetch_chaster_lock_runtime
from chastease.models import ChastitySession, Turn, User
from chastease.repositories.setup_store import load_sessions, save_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)
CHASTER_TIMER_SYNC_INTERVAL_SECONDS = 60


def _latest_setup_session_for_user(user_id: str) -> tuple[str, dict] | tuple[None, None]:
    store = load_sessions()
    candidates = []
    for sid, sess in store.items():
        if not isinstance(sess, dict):
            continue
        if sess.get("user_id") != user_id:
            continue
        if sess.get("status") not in {"draft", "setup_in_progress", "configured"}:
            continue
        candidates.append((sid, sess))
    if not candidates:
        return (None, None)
    candidates.sort(key=lambda item: item[1].get("updated_at", item[1].get("created_at", "")), reverse=True)
    return candidates[0]


def _can_access_session_live(session_user_id: str, auth_token: str | None, ai_access_token: str | None, request: Request) -> str | None:
    if auth_token:
        token_user_id = resolve_user_id_from_token(auth_token, request)
        if token_user_id == session_user_id:
            return "wearer"

    configured_ai_token = str(getattr(request.app.state.config, "AI_SESSION_READ_TOKEN", "") or "").strip()
    if configured_ai_token and ai_access_token and secrets.compare_digest(ai_access_token, configured_ai_token):
        return "ai"

    return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_live_target_end_at(policy: dict) -> tuple[str | None, str]:
    runtime_timer = policy.get("runtime_timer") if isinstance(policy, dict) else {}
    runtime_timer = runtime_timer if isinstance(runtime_timer, dict) else {}
    effective_end_at = str(runtime_timer.get("effective_end_at") or "").strip()
    if effective_end_at:
        return effective_end_at, "runtime_timer.effective_end_at"

    contract = policy.get("contract") if isinstance(policy, dict) else {}
    contract = contract if isinstance(contract, dict) else {}
    for key in ("end_date", "proposed_end_date", "max_end_date", "min_end_date"):
        candidate = str(contract.get(key) or "").strip()
        if candidate:
            return candidate, f"contract.{key}"
    return None, "none"


def _safe_days_between(start_value: str | None, end_value: str | None) -> int | None:
    start_raw = str(start_value or "").strip()
    end_raw = str(end_value or "").strip()
    if not start_raw or not end_raw:
        return None
    try:
        start_date = date.fromisoformat(start_raw)
        end_date = date.fromisoformat(end_raw)
    except ValueError:
        return None
    return (end_date - start_date).days


def _maybe_sync_timer_with_chaster(db, session: ChastitySession, request: Request, *, force: bool = False) -> bool:
    if session is None or session.status != "active":
        return False
    if not session.policy_snapshot_json:
        return False

    try:
        policy = json.loads(session.policy_snapshot_json)
    except Exception:
        return False
    if not isinstance(policy, dict):
        return False

    integrations = [str(item).strip().lower() for item in (policy.get("integrations") or []) if str(item).strip()]
    if "chaster" not in integrations:
        return False

    integration_config = policy.get("integration_config") if isinstance(policy.get("integration_config"), dict) else {}
    chaster_cfg = integration_config.get("chaster") if isinstance(integration_config.get("chaster"), dict) else {}
    api_token = str(chaster_cfg.get("api_token") or "").strip()
    lock_id = str(chaster_cfg.get("lock_id") or "").strip()
    if not api_token or not lock_id:
        return False

    runtime_timer = policy.get("runtime_timer") if isinstance(policy.get("runtime_timer"), dict) else {}
    now = datetime.now(UTC)
    if not force:
        last_sync_raw = str(runtime_timer.get("last_chaster_sync_at") or "").strip()
        last_sync_at = _parse_iso_datetime(last_sync_raw)
        if last_sync_at is not None:
            age_seconds = (now - last_sync_at).total_seconds()
            if age_seconds < CHASTER_TIMER_SYNC_INTERVAL_SECONDS:
                return False

    base_url = str(chaster_cfg.get("api_base") or getattr(request.app.state.config, "CHASTER_API_BASE", "https://api.chaster.app") or "").strip()
    try:
        runtime = asyncio.run(
            fetch_chaster_lock_runtime(
                api_base=base_url,
                api_token=api_token,
                lock_id=lock_id,
            )
        )
    except Exception as exc:
        logger.debug("Chaster timer sync failed for session %s: %s", session.id, exc)
        return False

    if not isinstance(runtime, dict):
        return False

    runtime_timer = dict(runtime_timer) if isinstance(runtime_timer, dict) else {}
    runtime_timer["last_chaster_sync_at"] = now.isoformat()

    changed = False
    target_end_at_raw = str(runtime.get("target_end_at") or "").strip() or None
    remaining_seconds = runtime.get("remaining_seconds")
    if remaining_seconds is not None:
        try:
            remaining_seconds = max(0, int(remaining_seconds))
        except Exception:
            remaining_seconds = None

    if target_end_at_raw:
        parsed_target = _parse_iso_datetime(target_end_at_raw)
        if parsed_target is not None:
            target_end_at_raw = parsed_target.isoformat()
    elif remaining_seconds is not None:
        target_end_at_raw = (now + timedelta(seconds=remaining_seconds)).isoformat()

    if runtime.get("has_active_session") and target_end_at_raw:
        if str(runtime_timer.get("effective_end_at") or "").strip() != target_end_at_raw:
            runtime_timer["effective_end_at"] = target_end_at_raw
            changed = True
        runtime_timer["state"] = "running"
        runtime_timer["paused_at"] = None
        runtime_timer["source"] = "chaster"
        runtime_timer["chaster_lock_id"] = str(runtime.get("lock_id") or lock_id)
        raw_status = str(runtime.get("raw_status") or "").strip()
        if raw_status:
            runtime_timer["chaster_status"] = raw_status
        if remaining_seconds is not None:
            runtime_timer["remaining_seconds"] = remaining_seconds
            changed = True
    elif runtime.get("has_active_session"):
        # We know there is an active lock, but no timing info could be extracted.
        runtime_timer["source"] = "chaster"
        runtime_timer["chaster_lock_id"] = str(runtime.get("lock_id") or lock_id)
        raw_status = str(runtime.get("raw_status") or "").strip()
        if raw_status:
            runtime_timer["chaster_status"] = raw_status

    policy["runtime_timer"] = runtime_timer
    updated_json = json.dumps(policy)
    if updated_json != (session.policy_snapshot_json or ""):
        session.policy_snapshot_json = updated_json
        session.updated_at = now
        db.add(session)
        db.commit()
        changed = True

    return changed


def _build_live_time_context(policy: dict, server_now: datetime) -> dict:
    runtime_timer = policy.get("runtime_timer") if isinstance(policy, dict) else {}
    runtime_timer = runtime_timer if isinstance(runtime_timer, dict) else {}
    timer_state = str(runtime_timer.get("state") or "running").strip().lower() or "running"
    is_paused = timer_state == "paused"

    contract = policy.get("contract") if isinstance(policy, dict) else {}
    contract = contract if isinstance(contract, dict) else {}
    contract_start_date = str(contract.get("start_date") or "").strip() or None
    contract_min_end_date = str(contract.get("min_end_date") or "").strip() or None
    contract_max_end_date = str(contract.get("max_end_date") or "").strip() or None
    contract_proposed_end_date = str(contract.get("proposed_end_date") or "").strip() or None
    contract_end_date = str(contract.get("end_date") or "").strip() or None

    target_end_at_raw, target_source = _resolve_live_target_end_at(policy)
    target_end_at = _parse_iso_datetime(target_end_at_raw)

    remaining_seconds: int | None = None
    if timer_state == "paused":
        paused_remaining = runtime_timer.get("remaining_seconds")
        if isinstance(paused_remaining, (int, float)):
            remaining_seconds = max(0, int(paused_remaining))
    elif target_end_at is not None:
        remaining_seconds = max(0, int(math.floor((target_end_at - server_now).total_seconds())))

    is_overdue = False
    if target_end_at is not None and timer_state != "paused":
        is_overdue = target_end_at <= server_now

    return {
        "timer_state": timer_state,
        "is_paused": is_paused,
        "target_end_at": (target_end_at.isoformat() if target_end_at is not None else target_end_at_raw),
        "target_source": target_source,
        "remaining_seconds": remaining_seconds,
        "is_overdue": is_overdue,
        "paused_at": runtime_timer.get("paused_at"),
        "contract_start_date": contract_start_date,
        "contract_min_end_date": contract_min_end_date,
        "contract_max_end_date": contract_max_end_date,
        "contract_proposed_end_date": contract_proposed_end_date,
        "contract_end_date": contract_end_date,
        "contract_min_duration_days": _safe_days_between(contract_start_date, contract_min_end_date),
        "contract_max_duration_days": _safe_days_between(contract_start_date, contract_max_end_date),
        "contract_target_duration_days": _safe_days_between(
            contract_start_date,
            contract_end_date or contract_proposed_end_date,
        ),
        "runtime_timer": runtime_timer,
    }


def _resolve_setup_context(user_id: str, session_id: str) -> dict:
    store = load_sessions()
    linked_setup_session_id = find_setup_session_id_for_active_session(user_id, session_id)
    linked_setup_session = store.get(linked_setup_session_id) if linked_setup_session_id else None

    latest_setup_session_id = None
    latest_setup_session = None
    if isinstance(store, dict):
        latest_setup_session_id, latest_setup_session = _latest_setup_session_for_user(user_id)

    return {
        "linked_setup_session_id": linked_setup_session_id,
        "linked_setup_session": _sanitize_setup_session_for_live(linked_setup_session),
        "latest_setup_session_id": latest_setup_session_id,
        "latest_setup_session": _sanitize_setup_session_for_live(latest_setup_session),
    }


def _sanitize_setup_session_for_live(setup_session: dict | None) -> dict | None:
    if not isinstance(setup_session, dict):
        return None

    sanitized = json.loads(json.dumps(setup_session))
    policy_preview = sanitized.get("policy_preview")
    if isinstance(policy_preview, dict):
        generated_contract = policy_preview.get("generated_contract")
        if isinstance(generated_contract, dict):
            full_text = str(generated_contract.get("text") or "")
            generated_contract["text"] = None
            generated_contract["text_omitted"] = bool(full_text)
            generated_contract["text_length"] = len(full_text)
    return sanitized


@router.get("/active")
def get_active_chastity_session(user_id: str, auth_token: str, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        session = db.scalar(
            select(ChastitySession)
            .where(ChastitySession.user_id == user_id)
            .where(ChastitySession.status == "active")
            .order_by(ChastitySession.created_at.desc())
        )
        if session is None:
            existing_setup_id, existing_setup = _latest_setup_session_for_user(user_id)
            if existing_setup is not None:
                return {
                    "has_active_session": False,
                    "setup_session_id": existing_setup_id,
                    "setup_status": existing_setup.get("status", "draft"),
                }
            draft_id, draft_session = find_or_create_draft_setup_session(user_id, "de")
            return {
                "has_active_session": False,
                "setup_session_id": draft_id,
                "setup_status": draft_session["status"],
            }

        _maybe_sync_timer_with_chaster(db, session, request, force=False)

        setup_session_id = find_setup_session_id_for_active_session(user_id, session.id)
        setup_status = "configured"
        if setup_session_id:
            store = load_sessions()
            linked_setup = store.get(setup_session_id) or {}
            setup_status = linked_setup.get("status", setup_status)
        return {
            "has_active_session": True,
            "setup_session_id": setup_session_id,
            "setup_status": setup_status,
            "chastity_session": serialize_chastity_session(session),
        }
    finally:
        db.close()


@router.post("/{session_id}/integrations")
def update_active_session_integrations(
    session_id: str,
    payload: SetupIntegrationsUpdateRequest,
    request: Request,
) -> dict:
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    normalized_integrations = [str(item).strip().lower() for item in (payload.integrations or []) if str(item).strip()]
    integration_config = payload.integration_config if isinstance(payload.integration_config, dict) else {}
    if "chaster" in normalized_integrations:
        chaster_cfg = integration_config.get("chaster") if isinstance(integration_config, dict) else None
        if isinstance(chaster_cfg, dict):
            api_token = str(chaster_cfg.get("api_token") or "").strip()
            if not api_token:
                raise HTTPException(
                    status_code=400,
                    detail="integration_config.chaster requires api_token.",
                )

    db = get_db_session(request)
    try:
        user = db.get(User, payload.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        if session.user_id != payload.user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user.")
        if session.status != "active":
            raise HTTPException(status_code=409, detail="Session is not active.")

        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        policy["integrations"] = normalized_integrations
        policy["integration_config"] = integration_config

        session.policy_snapshot_json = json.dumps(policy)
        session.updated_at = datetime.now(UTC)
        db.add(session)
        db.commit()

        applied_to_setup_session = False
        setup_session_id = find_setup_session_id_for_active_session(payload.user_id, session_id)
        if setup_session_id:
            store = load_sessions()
            setup_session = store.get(setup_session_id)
            if isinstance(setup_session, dict) and setup_session.get("user_id") == payload.user_id:
                setup_session["integrations"] = normalized_integrations
                setup_session["integration_config"] = integration_config
                if isinstance(setup_session.get("policy_preview"), dict):
                    setup_session["policy_preview"]["integrations"] = normalized_integrations
                    setup_session["policy_preview"]["integration_config"] = integration_config
                setup_session["updated_at"] = datetime.now(UTC).isoformat()
                store[setup_session_id] = setup_session
                save_sessions(store)
                applied_to_setup_session = True

        return {
            "session_id": session_id,
            "integrations": normalized_integrations,
            "integration_config": integration_config,
            "applied_to_setup_session": applied_to_setup_session,
        }
    finally:
        db.close()


@router.delete("/active")
def kill_active_chastity_session(
    user_id: str, auth_token: str, request: Request, setup_session_id: str | None = None
) -> dict:
    if not getattr(request.app.state.config, "ENABLE_SESSION_KILL", False):
        raise HTTPException(status_code=404, detail="Not found.")

    token_user_id = resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        session = db.scalar(
            select(ChastitySession)
            .where(ChastitySession.user_id == user_id)
            .where(ChastitySession.status == "active")
            .order_by(ChastitySession.created_at.desc())
        )
        deleted = False
        killed_session_id = None
        inferred_setup_session_id = None
        if session is not None:
            inferred_setup_session_id = find_setup_session_id_for_active_session(user_id, session.id)
            turns = db.scalars(select(Turn).where(Turn.session_id == session.id)).all()
            for turn in turns:
                db.delete(turn)
            killed_session_id = session.id
            db.delete(session)
            deleted = True
        db.commit()

        deleted_setup_session = False
        target_setup_session_id = setup_session_id or inferred_setup_session_id
        if target_setup_session_id:
            store = load_sessions()
            setup_session = store.get(target_setup_session_id)
            if setup_session and setup_session.get("user_id") == user_id:
                del store[target_setup_session_id]
                save_sessions(store)
                deleted_setup_session = True

        draft_id, draft_session = find_or_create_draft_setup_session(user_id, "de")
        if not deleted and not deleted_setup_session:
            return {
                "deleted": False,
                "reason": "no_active_or_setup_session",
                "setup_session_id": draft_id,
                "setup_status": draft_session["status"],
            }
        return {
            "deleted": deleted or deleted_setup_session,
            "killed_session_id": killed_session_id,
            "deleted_setup_session": deleted_setup_session,
            "setup_session_id": draft_id,
            "setup_status": draft_session["status"],
        }
    finally:
        db.close()


@router.get("/{session_id}")
def get_chastity_session(session_id: str, request: Request) -> dict:
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        return serialize_chastity_session(session)
    finally:
        db.close()


@router.get("/{session_id}/turns")
def get_session_turns(session_id: str, request: Request) -> dict:
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        turns = db.scalars(
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(Turn.turn_no)
        ).all()
        return {
            "session_id": session_id,
            "turns": [
                {
                    "turn_no": turn.turn_no,
                    "player_action": turn.player_action,
                    "ai_narration": turn.ai_narration,
                    "language": turn.language,
                    "created_at": iso_utc(turn.created_at),
                }
                for turn in turns
            ],
        }
    finally:
        db.close()


@router.get("/{session_id}/live")
def get_live_session_info(
    session_id: str,
    request: Request,
    auth_token: str | None = None,
    recent_turns_limit: int = 5,
    detail_level: str = "light",
) -> dict:
    """
    Retrieve live session information.

    detail_level:
      - 'light': Only session_status and time_context (minimal token usage)
      - 'full': Includes setup_context, turns, and full session object

    AI access token must be supplied via the X-AI-Access-Token header.
    """
    ai_access_token = request.headers.get("X-AI-Access-Token") or request.headers.get("x-ai-access-token")
    detail_mode = str(detail_level).strip().lower()
    if detail_mode not in ("light", "full"):
        detail_mode = "light"
    
    turn_limit = max(1, min(25, int(recent_turns_limit)))
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        access_mode = _can_access_session_live(session.user_id, auth_token, ai_access_token, request)
        if access_mode is None:
            raise HTTPException(status_code=401, detail="Invalid token for live session read.")

        _maybe_sync_timer_with_chaster(db, session, request, force=False)

        server_now = datetime.now(UTC)
        session_payload = serialize_chastity_session(session)
        policy = session_payload.get("policy") if isinstance(session_payload, dict) else {}
        policy = policy if isinstance(policy, dict) else {}
        time_context = _build_live_time_context(policy, server_now)

        response = {
            "request_id": str(uuid4()),
            "server_time": server_now.isoformat(),
            "access_mode": access_mode,
            "detail_level": detail_mode,
            "session_status": {
                "status": session.status,
                "language": session.language,
                "updated_at": iso_utc(session.updated_at),
            },
            "time_context": time_context,
        }

        if detail_mode == "full":
            total_turns = int(
                db.scalar(select(func.count()).select_from(Turn).where(Turn.session_id == session_id)) or 0
            )
            turns = db.scalars(
                select(Turn)
                .where(Turn.session_id == session_id)
                .order_by(desc(Turn.turn_no))
                .limit(turn_limit)
            ).all()
            setup_context = _resolve_setup_context(session.user_id, session.id)
            
            response["session"] = session_payload
            response["setup_context"] = setup_context
            response["turns"] = {
                "total": total_turns,
                "returned": len(turns),
                "items": [
                    {
                        "turn_no": turn.turn_no,
                        "player_action": turn.player_action,
                        "ai_narration": turn.ai_narration,
                        "language": turn.language,
                        "created_at": iso_utc(turn.created_at),
                    }
                    for turn in turns
                ],
            }

        return response
    finally:
        db.close()
