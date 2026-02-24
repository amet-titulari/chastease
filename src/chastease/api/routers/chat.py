import base64
import json
import logging
import re
import time
from pathlib import Path
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api.runtime import get_db_session, lang
from chastease.api.schemas import ChatActionExecuteRequest, ChatTurnRequest, ChatVisionReviewRequest
from chastease.models import ChastitySession, Turn
from chastease.services.narration import extract_pending_actions, generate_ai_narration_for_session

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

_DURATION_UNIT_SECONDS = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 3600,
    "hours": 3600,
    "day": 86400,
    "days": 86400,
}
_TIMER_ACTIONS = {"pause_timer", "unpause_timer", "add_time", "reduce_time"}
_TTLOCK_ACTIONS = {"ttlock_open", "ttlock_close"}
_HYGIENE_ACTIONS = {"hygiene_open", "hygiene_close"}
_ACTION_ALIASES = {
    "addtime": "add_time",
    "reducetime": "reduce_time",
    "pausetimer": "pause_timer",
    "unpausetimer": "unpause_timer",
    "hygieneopen": "hygiene_open",
    "hygieneclose": "hygiene_close",
    "imageverification": "image_verification",
    "verifyimage": "image_verification",
    "visionreview": "image_verification",
}
_ACTION_WRAPPERS = {"suggest", "request", "execute", "tool", "action"}
_DURATION_PATTERN = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "stunde": 3600,
    "stunden": 3600,
    "tag": 86400,
    "tage": 86400,
}
_IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_utc(value: datetime) -> str:
    return _to_utc(value).isoformat()


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return _to_utc(datetime.fromisoformat(text))
        parsed_date = date.fromisoformat(text)
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day, 23, 59, 59, tzinfo=UTC)
    except Exception:
        return None


def _format_contract_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _to_utc(value).date().isoformat()


def _seed_timer_from_contract(contract: dict, now: datetime) -> dict:
    start_at = _parse_iso_dt(contract.get("start_date")) or now
    end_at = (
        _parse_iso_dt(contract.get("proposed_end_date"))
        or _parse_iso_dt(contract.get("end_date"))
        or _parse_iso_dt(contract.get("max_end_date"))
        or _parse_iso_dt(contract.get("min_end_date"))
        or (now + timedelta(days=1))
    )
    min_end_at = _parse_iso_dt(contract.get("min_end_date"))
    max_end_at = _parse_iso_dt(contract.get("max_end_date"))
    return {
        "state": "running",
        "started_at": _iso_utc(start_at),
        "effective_end_at": _iso_utc(end_at),
        "min_end_at": _iso_utc(min_end_at) if min_end_at else None,
        "max_end_at": _iso_utc(max_end_at) if max_end_at else None,
        "paused_at": None,
        "last_action": "init",
        "last_action_at": _iso_utc(now),
    }


def _ensure_timer_state(policy: dict, now: datetime) -> dict:
    timer = policy.get("runtime_timer") if isinstance(policy.get("runtime_timer"), dict) else {}
    if not timer or not timer.get("effective_end_at"):
        contract = policy.get("contract") if isinstance(policy.get("contract"), dict) else {}
        timer = _seed_timer_from_contract(contract, now)
    timer.setdefault("state", "running")
    timer.setdefault("paused_at", None)
    timer.setdefault("started_at", _iso_utc(now))
    timer.setdefault("last_action", "init")
    timer.setdefault("last_action_at", _iso_utc(now))
    return timer


def _remaining_seconds(timer: dict, now: datetime) -> int:
    end_at = _parse_iso_dt(timer.get("effective_end_at"))
    if end_at is None:
        return 0
    if timer.get("state") == "paused" and timer.get("paused_at"):
        ref = _parse_iso_dt(timer.get("paused_at")) or now
    else:
        ref = now
    return max(0, int((end_at - ref).total_seconds()))


def _apply_timer_action(action_type: str, payload: dict, policy: dict, now: datetime) -> tuple[dict, dict, str]:
    contract = policy.setdefault("contract", {})
    timer = _ensure_timer_state(policy, now)
    action = action_type.strip().lower()

    effective_end_at = _parse_iso_dt(timer.get("effective_end_at")) or now
    min_end_at = _parse_iso_dt(timer.get("min_end_at"))
    max_end_at = _parse_iso_dt(timer.get("max_end_at"))
    paused_at = _parse_iso_dt(timer.get("paused_at"))

    if action == "pause_timer":
        if timer.get("state") != "paused":
            timer["state"] = "paused"
            timer["paused_at"] = _iso_utc(now)
        timer["last_action"] = "pause_timer"
        timer["last_action_at"] = _iso_utc(now)
        message = "Timer paused."
    elif action == "unpause_timer":
        if timer.get("state") == "paused" and paused_at is not None:
            paused_seconds = max(0, int((now - paused_at).total_seconds()))
            next_end_at = effective_end_at + timedelta(seconds=paused_seconds)
            if max_end_at is not None and next_end_at > max_end_at:
                next_end_at = max_end_at
            effective_end_at = next_end_at
            timer["effective_end_at"] = _iso_utc(effective_end_at)
        timer["state"] = "running"
        timer["paused_at"] = None
        timer["last_action"] = "unpause_timer"
        timer["last_action_at"] = _iso_utc(now)
        message = "Timer resumed."
    elif action == "add_time":
        seconds = int(payload.get("seconds", 0))
        if seconds <= 0:
            raise HTTPException(status_code=400, detail="Action 'add_time' requires seconds > 0.")
        next_end_at = effective_end_at + timedelta(seconds=seconds)
        if max_end_at is not None and next_end_at > max_end_at:
            next_end_at = max_end_at
        effective_end_at = next_end_at
        timer["effective_end_at"] = _iso_utc(effective_end_at)
        timer["last_action"] = "add_time"
        timer["last_action_at"] = _iso_utc(now)
        message = "Time added."
    elif action == "reduce_time":
        seconds = int(payload.get("seconds", 0))
        if seconds <= 0:
            raise HTTPException(status_code=400, detail="Action 'reduce_time' requires seconds > 0.")
        next_end_at = effective_end_at - timedelta(seconds=seconds)
        if min_end_at is not None and next_end_at < min_end_at:
            raise HTTPException(status_code=400, detail="Action 'reduce_time' exceeds min_end_date boundary.")
        effective_end_at = next_end_at
        timer["effective_end_at"] = _iso_utc(effective_end_at)
        timer["last_action"] = "reduce_time"
        timer["last_action_at"] = _iso_utc(now)
        message = "Time reduced."
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action_type '{action_type}'.")

    contract["proposed_end_date"] = _format_contract_date(effective_end_at)
    timer["remaining_seconds"] = _remaining_seconds(timer, now)
    policy["runtime_timer"] = timer
    return policy, timer, message


def _to_int(value) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid duration values")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return int(value.strip())
    raise ValueError("duration value must be integer-like")


def _normalize_action_type(action_type: str) -> str:
    raw = str(action_type or "").strip().lower()
    if not raw:
        return ""
    return _ACTION_ALIASES.get(raw, raw)


def _parse_duration_seconds(raw_value: str) -> int | None:
    text = str(raw_value or "").strip().lower()
    if not text:
        return None
    import re

    match = re.match(
        r"^(?P<amount>\d+)\s*(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|stunde|stunden|tag|tage)?$",
        text,
    )
    if not match:
        return None
    amount = int(match.group("amount"))
    unit = match.group("unit") or "s"
    return amount * _DURATION_PATTERN.get(unit, 1)


def _unwrap_action_request(action_type: str, payload: dict) -> tuple[str, dict]:
    normalized_action = _normalize_action_type(action_type)
    normalized_payload = dict(payload or {})
    if normalized_action in _ACTION_WRAPPERS:
        nested = (
            normalized_payload.get("action_type")
            or normalized_payload.get("action")
            or normalized_payload.get("tool")
            or normalized_payload.get("request")
        )
        resolved = _normalize_action_type(str(nested or ""))
        if resolved:
            normalized_action = resolved
            for key in ("action_type", "action", "tool", "request"):
                normalized_payload.pop(key, None)
    return normalized_action, normalized_payload


def _safe_stem(name: str) -> str:
    stem = Path(str(name or "image")).stem
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_")
    return cleaned[:60] or "image"


def _extension_from_content_type(content_type: str, picture_name: str) -> str:
    ext = _IMAGE_EXTENSIONS.get(str(content_type).lower())
    if ext:
        return ext
    suffix = Path(str(picture_name or "")).suffix.strip().lower()
    if suffix.startswith(".") and len(suffix) <= 10:
        return suffix
    return ".jpg"


def _save_verification_image(
    *,
    request: Request,
    session_id: str,
    picture_name: str,
    picture_content_type: str,
    image_bytes: bytes,
) -> str:
    configured_dir = str(getattr(request.app.state.config, "IMAGE_VERIFICATION_DIR", "data/image_verifications"))
    base_dir = Path(configured_dir)
    if not base_dir.is_absolute():
        base_dir = Path.cwd() / base_dir
    target_dir = base_dir / session_id
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"{stamp}_{_safe_stem(picture_name)}{_extension_from_content_type(picture_content_type, picture_name)}"
    target_path = target_dir / filename
    target_path.write_bytes(image_bytes)
    return str(target_path)


def _normalize_pending_actions(pending_actions: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for action in pending_actions:
        raw_action_type = str((action or {}).get("action_type") or "")
        payload = (action or {}).get("payload")
        payload_dict = dict(payload) if isinstance(payload, dict) else {}
        normalized_action, normalized_payload = _unwrap_action_request(raw_action_type, payload_dict)
        normalized.append(
            {
                "action_type": normalized_action or raw_action_type,
                "payload": normalized_payload,
                "requires_execute_call": bool((action or {}).get("requires_execute_call", True)),
            }
        )
    return normalized


def _normalize_duration_payload(action_type: str, payload: dict) -> dict:
    action = _normalize_action_type(action_type)
    if action not in {"add_time", "reduce_time"}:
        return dict(payload or {})

    data = dict(payload or {})
    if "seconds" in data:
        seconds = _to_int(data.get("seconds"))
        if seconds <= 0:
            raise HTTPException(status_code=400, detail=f"Action '{action}' requires seconds > 0.")
        return {"seconds": seconds}

    if "amount" in data and "unit" in data:
        amount = _to_int(data.get("amount"))
        unit = str(data.get("unit") or "").strip().lower()
        factor = _DURATION_UNIT_SECONDS.get(unit)
        if factor is None:
            raise HTTPException(
                status_code=400,
                detail="Duration unit must be one of: seconds, minutes, hours, days.",
            )
        seconds = amount * factor
        if seconds <= 0:
            raise HTTPException(status_code=400, detail=f"Action '{action}' requires a positive duration.")
        return {"seconds": seconds}

    # Backward-compatible convenience fields accepted from AI payloads.
    if "duration" in data:
        seconds = _parse_duration_seconds(str(data.get("duration") or ""))
        if seconds is None or seconds <= 0:
            raise HTTPException(status_code=400, detail=f"Action '{action}' requires a valid duration.")
        return {"seconds": seconds}

    for key in ("minutes", "hours", "days"):
        if key in data:
            amount = _to_int(data.get(key))
            seconds = amount * _DURATION_UNIT_SECONDS[key]
            if seconds <= 0:
                raise HTTPException(status_code=400, detail=f"Action '{action}' requires a positive duration.")
            return {"seconds": seconds}

    raise HTTPException(
        status_code=400,
        detail=(
            f"Action '{action}' requires a duration payload. "
            "Use either {seconds} or {amount, unit} with unit in seconds/minutes/hours/days."
        ),
    )


def _ttlock_from_policy(policy: dict) -> dict:
    integration_config = policy.get("integration_config")
    if not isinstance(integration_config, dict):
        return {}
    ttlock = integration_config.get("ttlock")
    return ttlock if isinstance(ttlock, dict) else {}


def _retry_delay_seconds(attempt: int, retry_after_header: str | None = None) -> float:
    if retry_after_header:
        raw = str(retry_after_header).strip()
        if raw:
            try:
                seconds = float(raw)
                if seconds > 0:
                    return min(seconds, 10.0)
            except ValueError:
                pass
    base = min(0.6 * (2 ** max(0, attempt - 1)), 4.0)
    jitter = 0.1 * attempt
    return base + jitter


def _ttlock_access_token(
    *,
    base_url: str,
    client_id: str,
    client_secret: str,
    ttl_user: str,
    ttl_pass_md5: str,
) -> str:
    url = f"{base_url.rstrip('/')}/oauth2/token"
    data = {
        "grant_type": "password",
        "clientId": client_id,
        "clientSecret": client_secret,
        "username": ttl_user,
        "password": ttl_pass_md5,
    }
    timeout = httpx.Timeout(connect=5.0, read=20.0, write=15.0, pool=5.0)
    retryable = {408, 409, 421, 425, 429, 500, 502, 503, 504}
    last_error = "TT-Lock auth failed"
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            if resp.status_code >= 400:
                body_text = resp.text[:220].strip()
                if resp.status_code in retryable and attempt < 3:
                    delay = _retry_delay_seconds(attempt, resp.headers.get("retry-after"))
                    time.sleep(delay)
                    continue
                raise HTTPException(
                    status_code=400,
                    detail=f"TT-Lock auth HTTP {resp.status_code}{(': ' + body_text) if body_text else ''}",
                )
            body = resp.json()
            if body.get("errcode", 0) not in (0, "0"):
                last_error = f"TT-Lock auth failed: {body.get('errmsg', 'unknown error')}"
                if attempt < 3:
                    time.sleep(_retry_delay_seconds(attempt))
                    continue
                raise HTTPException(status_code=400, detail=last_error)
            token = str(body.get("access_token") or "").strip()
            if token:
                return token
            last_error = "TT-Lock auth returned no access_token."
        except httpx.TimeoutException:
            last_error = "TT-Lock auth timeout."
            if attempt < 3:
                time.sleep(_retry_delay_seconds(attempt))
                continue
        except httpx.HTTPError as exc:
            last_error = f"TT-Lock auth transport error: {exc.__class__.__name__}"
            if attempt < 3:
                time.sleep(_retry_delay_seconds(attempt))
                continue
    raise HTTPException(status_code=400, detail=last_error)


def _ttlock_command(
    *,
    base_url: str,
    client_id: str,
    access_token: str,
    lock_id: str,
    command: str,
) -> dict:
    endpoint = "unlock" if command == "open" else "lock"
    url = f"{base_url.rstrip('/')}/v3/lock/{endpoint}"
    timeout = httpx.Timeout(connect=5.0, read=35.0, write=20.0, pool=5.0)
    retryable = {408, 409, 421, 425, 429, 500, 502, 503, 504}
    last_error = f"TT-Lock {endpoint} failed"
    for attempt in range(1, 4):
        params = {
            "clientId": client_id,
            "accessToken": access_token,
            "lockId": lock_id,
            "date": int(time.time() * 1000),
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
            if resp.status_code >= 400:
                body_text = resp.text[:220].strip()
                if resp.status_code in retryable and attempt < 3:
                    delay = _retry_delay_seconds(attempt, resp.headers.get("retry-after"))
                    time.sleep(delay)
                    continue
                raise HTTPException(
                    status_code=400,
                    detail=f"TT-Lock {endpoint} HTTP {resp.status_code}{(': ' + body_text) if body_text else ''}",
                )
            body = resp.json()
            if body.get("errcode", 0) not in (0, "0"):
                last_error = f"TT-Lock {endpoint} failed: {body.get('errmsg', 'unknown error')}"
                if attempt < 3:
                    time.sleep(_retry_delay_seconds(attempt))
                    continue
                raise HTTPException(status_code=400, detail=last_error)
            return body
        except httpx.TimeoutException:
            last_error = f"TT-Lock {endpoint} timeout."
            if attempt < 3:
                time.sleep(_retry_delay_seconds(attempt))
                continue
        except httpx.HTTPError as exc:
            last_error = f"TT-Lock {endpoint} transport error: {exc.__class__.__name__}"
            if attempt < 3:
                time.sleep(_retry_delay_seconds(attempt))
                continue
    raise HTTPException(status_code=400, detail=last_error)


def _execute_ttlock_action(
    *,
    action_type: str,
    payload: dict,
    policy: dict,
    request: Request,
) -> tuple[dict, dict]:
    config = _ttlock_from_policy(policy)
    integrations = [str(x).strip().lower() for x in (policy.get("integrations") or []) if str(x).strip()]
    if "ttlock" not in integrations and not config:
        raise HTTPException(status_code=400, detail="TT-Lock integration is not enabled in this session policy.")

    ttl_user = str(config.get("ttl_user") or "").strip()
    ttl_pass_md5 = str(config.get("ttl_pass_md5") or "").strip().lower()
    lock_id = str(payload.get("ttl_lock_id") or payload.get("lock_id") or config.get("ttl_lock_id") or "").strip()
    gateway_id = str(config.get("ttl_gateway_id") or "").strip() or None
    if not ttl_user or not ttl_pass_md5 or not lock_id:
        raise HTTPException(
            status_code=400,
            detail="TT-Lock configuration incomplete. Required: ttl_user, ttl_pass_md5, ttl_lock_id.",
        )

    client_id = str(getattr(request.app.state.config, "TTL_CLIENT_ID", "") or "").strip()
    client_secret = str(getattr(request.app.state.config, "TTL_CLIENT_SECRET", "") or "").strip()
    base_url = str(getattr(request.app.state.config, "TTL_API_BASE", "https://euapi.ttlock.com") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="TT-Lock server config missing: TTL_CLIENT_ID / TTL_CLIENT_SECRET.")

    command = "open" if str(action_type).endswith("_open") else "close"
    access_token = _ttlock_access_token(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        ttl_user=ttl_user,
        ttl_pass_md5=ttl_pass_md5,
    )
    result_payload = _ttlock_command(
        base_url=base_url,
        client_id=client_id,
        access_token=access_token,
        lock_id=lock_id,
        command=command,
    )
    logger.info(
        "TT-Lock command executed: action=%s lock_id=%s gateway_id=%s",
        action_type,
        lock_id,
        gateway_id or "-",
    )
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    opening_window_minutes = int(limits.get("opening_window_minutes") or 15)
    opening_window_minutes = max(1, min(opening_window_minutes, 240))
    opening_window_seconds = opening_window_minutes * 60
    window_end_at = (
        _iso_utc(datetime.now(UTC) + timedelta(seconds=opening_window_seconds))
        if command == "open"
        else None
    )
    return policy, {
        "action_type": action_type,
        "payload": {
            "lock_id": lock_id,
            "opening_window_minutes": opening_window_minutes,
            "opening_window_seconds": opening_window_seconds,
            "window_end_at": window_end_at,
        },
        "ttlock": {
            "command": command,
            "lock_id": lock_id,
            "gateway_id": gateway_id,
            "response": result_payload,
        },
        "message": (
            f"TT-Lock opened. Hygiene window: {opening_window_minutes} minute(s)."
            if command == "open"
            else "TT-Lock closed."
        ),
    }


def _execute_action_with_policy(
    *,
    action_type: str,
    payload: dict,
    policy: dict,
    request: Request,
    now: datetime,
) -> tuple[dict, dict]:
    normalized_action, unwrapped_payload = _unwrap_action_request(action_type, payload)
    normalized_payload = _normalize_duration_payload(normalized_action, unwrapped_payload)
    if normalized_action in _TIMER_ACTIONS:
        updated_policy, timer_state, action_message = _apply_timer_action(
            normalized_action,
            normalized_payload,
            policy,
            now,
        )
        return updated_policy, {
            "action_type": normalized_action,
            "payload": normalized_payload,
            "timer": timer_state,
            "message": action_message,
        }
    if normalized_action in _TTLOCK_ACTIONS:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Action '{normalized_action}' is reserved for system-managed session lifecycle. "
                "Use 'hygiene_open' or 'hygiene_close' for interactive hygiene flows."
            ),
        )
    if normalized_action in _HYGIENE_ACTIONS:
        return _execute_ttlock_action(
            action_type=normalized_action,
            payload=normalized_payload,
            policy=policy,
            request=request,
        )
    if normalized_action == "image_verification":
        raise HTTPException(
            status_code=400,
            detail="Action 'image_verification' requires user submission from the chat action card.",
        )
    raise HTTPException(status_code=400, detail=f"Unsupported action_type '{normalized_action}'.")


def _autonomy_mode_from_policy(policy: dict) -> str:
    mode = str((policy or {}).get("autonomy_mode") or "execute").strip().lower()
    return "execute" if mode == "execute" else "suggest"


def _auto_execute_pending_actions(
    *,
    request: Request,
    policy: dict,
    pending_actions: list[dict],
) -> tuple[list[dict], list[dict], list[dict], dict]:
    normalized_pending = _normalize_pending_actions(pending_actions)
    mode = _autonomy_mode_from_policy(policy)
    if not normalized_pending:
        return normalized_pending, [], [], policy

    registry = getattr(request.app.state, "tool_registry", None)
    now = datetime.now(UTC)
    remaining_actions: list[dict] = []
    executed_actions: list[dict] = []
    failed_actions: list[dict] = []
    updated_policy = dict(policy)

    for action in normalized_pending:
        normalized_action = _normalize_action_type(str((action or {}).get("action_type") or ""))
        payload = (action or {}).get("payload")
        payload_dict = dict(payload) if isinstance(payload, dict) else {}
        should_execute = mode == "execute"

        if not normalized_action:
            failed_actions.append({"action_type": "", "payload": payload_dict, "detail": "Missing action_type."})
            continue
        if not should_execute:
            remaining_actions.append(action)
            continue
        if registry is not None and not registry.is_allowed(normalized_action, mode="execute"):
            if registry.is_allowed(normalized_action, mode="suggest"):
                remaining_actions.append(action)
            else:
                failed_actions.append(
                    {
                        "action_type": normalized_action,
                        "payload": payload_dict,
                        "detail": f"Tool '{normalized_action}' is not allowed for execution.",
                    }
                )
            continue
        try:
            updated_policy, executed = _execute_action_with_policy(
                action_type=normalized_action,
                payload=payload_dict,
                policy=updated_policy,
                request=request,
                now=now,
            )
            executed_actions.append(executed)
        except HTTPException as exc:
            failed_actions.append(
                {"action_type": normalized_action, "payload": payload_dict, "detail": str(exc.detail)}
            )

    return remaining_actions, executed_actions, failed_actions, updated_policy


@router.post("/turn")
def chat_turn(payload: ChatTurnRequest, request: Request) -> dict:
    request_lang = lang(payload.language)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")

    action_text = message

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        narration_raw = generate_ai_narration_for_session(
            db, request, session, action_text, request_lang, payload.attachments
        )
        narration, pending_actions, generated_files = extract_pending_actions(narration_raw)
        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        pending_actions, executed_actions, failed_actions, updated_policy = _auto_execute_pending_actions(
            request=request,
            policy=policy,
            pending_actions=pending_actions,
        )
        if executed_actions:
            session.policy_snapshot_json = json.dumps(updated_policy)

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session.id))
        next_turn_no = (current_turn_no or 0) + 1
        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=action_text,
            ai_narration=narration,
            language=request_lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
        "pending_actions": pending_actions,
        "executed_actions": executed_actions,
        "failed_actions": failed_actions,
        "generated_files": generated_files,
        "next_state": "awaiting_wearer_action",
    }


@router.post("/vision-review")
def chat_vision_review(payload: ChatVisionReviewRequest, request: Request) -> dict:
    request_lang = lang(payload.language)
    prompt = payload.message.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")
    content_type = payload.picture_content_type.lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="picture_content_type must be image/*")
    if not payload.picture_data_url.startswith(f"data:{content_type};base64,"):
        raise HTTPException(status_code=400, detail="Invalid picture_data_url format.")
    image_b64 = payload.picture_data_url.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="picture too large (max 8MB)")
    attachments = [
        {
            "name": payload.picture_name or "image",
            "type": content_type,
            "size": len(image_bytes),
            "data_url": payload.picture_data_url,
        }
    ]
    saved_image_path = _save_verification_image(
        request=request,
        session_id=payload.session_id,
        picture_name=payload.picture_name,
        picture_content_type=content_type,
        image_bytes=image_bytes,
    )
    verification_instruction = str(payload.verification_instruction or "").strip()
    action_payload = payload.verification_action_payload if isinstance(payload.verification_action_payload, dict) else {}
    action_payload_json = json.dumps(action_payload, ensure_ascii=True)
    enriched_prompt = prompt
    if verification_instruction:
        enriched_prompt = (
            f"{enriched_prompt}\n\nVerification instruction:\n{verification_instruction}\n"
            "Please briefly describe what is visible in the image first, then evaluate if the verification instruction is fulfilled."
        )
    if action_payload:
        enriched_prompt = f"{enriched_prompt}\n\nVerification payload: {action_payload_json}"
    enriched_prompt = f"{enriched_prompt}\n\nImage source: {payload.source}"

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        narration_raw = generate_ai_narration_for_session(
            db, request, session, enriched_prompt, request_lang, attachments
        )
        narration, pending_actions, generated_files = extract_pending_actions(narration_raw)
        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        pending_actions, executed_actions, failed_actions, updated_policy = _auto_execute_pending_actions(
            request=request,
            policy=policy,
            pending_actions=pending_actions,
        )
        if executed_actions:
            session.policy_snapshot_json = json.dumps(updated_policy)

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session.id))
        next_turn_no = (current_turn_no or 0) + 1
        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=(
                f"{prompt} [image:{payload.picture_name or 'upload'}]"
                f" [source:{payload.source}] [stored:{saved_image_path}]"
            ),
            ai_narration=narration,
            language=request_lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
        "pending_actions": pending_actions,
        "executed_actions": executed_actions,
        "failed_actions": failed_actions,
        "generated_files": generated_files,
        "saved_image_path": saved_image_path,
        "next_state": "awaiting_wearer_action",
    }


@router.post("/actions/execute")
def chat_action_execute(payload: ChatActionExecuteRequest, request: Request) -> dict:
    normalized_action = _normalize_action_type(payload.action_type)
    registry = getattr(request.app.state, "tool_registry", None)
    if registry is not None and not registry.is_allowed(normalized_action, mode="execute"):
        raise HTTPException(status_code=403, detail=f"Tool '{normalized_action}' is not allowed for execution.")

    now = datetime.now(UTC)
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        updated_policy, result = _execute_action_with_policy(
            action_type=normalized_action,
            payload=payload.payload,
            policy=policy,
            request=request,
            now=now,
        )
        session.policy_snapshot_json = json.dumps(updated_policy)
        session.updated_at = now
        db.add(session)
        db.commit()
    finally:
        db.close()
    return {
        "executed": True,
        "session_id": payload.session_id,
        "action_type": result["action_type"],
        "payload": result["payload"],
        "timer": result.get("timer"),
        "ttlock": result.get("ttlock"),
        "message": result["message"],
    }
