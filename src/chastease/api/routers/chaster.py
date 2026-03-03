from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import random
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from chastease.api.setup_infra import resolve_user_id_from_token

router = APIRouter(prefix="/setup/chaster", tags=["setup"])


class ChasterCreateSessionRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    chaster_api_token: str = Field(min_length=8)
    code: str | None = Field(default=None, min_length=3, max_length=32)
    min_duration_minutes: int = Field(default=60, ge=1, le=525600)
    max_duration_minutes: int = Field(default=10080, ge=1, le=525600)
    min_limit_duration_minutes: int = Field(default=0, ge=0, le=525600)
    max_limit_duration_minutes: int = Field(default=0, ge=0, le=525600)
    display_remaining_time: bool = True
    limit_lock_time: bool = True
    allow_session_offer: bool = True
    is_test_lock: bool = False
    hide_time_logs: bool = True
    extensions: list[dict[str, Any]] = Field(default_factory=list)
    create_code_payload: dict[str, Any] = Field(default_factory=dict)
    create_lock_payload: dict[str, Any] = Field(default_factory=dict)


def _compact_json_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        try:
            import json
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


async def _post_json(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_detail = ""
    for attempt in range(1, 3):
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            transaction_id = str(response.headers.get("x-chaster-transaction-id") or "").strip()
            retry_after_raw = str(response.headers.get("retry-after") or "").strip()
            retry_after = int(retry_after_raw) if retry_after_raw.isdigit() else 0
            try:
                response_json = response.json()
                body_text = _compact_json_text(response_json)[:700].strip()
            except Exception:
                body_text = response.text[:700].strip()
            last_detail = (
                f"Chaster API POST {url} failed with HTTP {response.status_code}"
                f"{(' (tx=' + transaction_id + ')') if transaction_id else ''}"
                f"{(': ' + body_text) if body_text else ''}"
            )
            should_retry = response.status_code >= 500 and retry_after > 0 and attempt < 2
            if should_retry:
                await asyncio.sleep(max(1, min(retry_after, 15)))
                continue
            raise HTTPException(status_code=400, detail=last_detail)
        try:
            body = response.json()
        except Exception as exc:  # pragma: no cover - defensive branch
            raise HTTPException(status_code=400, detail=f"Chaster API returned non-JSON response for {url}.") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail=f"Chaster API returned unexpected response shape for {url}.")
        return body
    raise HTTPException(status_code=400, detail=last_detail or f"Chaster API POST {url} failed.")


def _nine_digit_code() -> str:
    return str(random.randint(100_000_000, 999_999_999))


def _extract_first_value(obj: Any, keys: set[str]) -> str | None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
        for value in obj.values():
            nested = _extract_first_value(value, keys)
            if nested:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = _extract_first_value(item, keys)
            if nested:
                return nested
    return None


def _sanitize_extensions(raw: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in list(raw or []):
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        cfg = item.get("config")
        result.append(
            {
                "slug": slug,
                "config": cfg if isinstance(cfg, dict) else {},
            }
        )
    return result


@router.post("/create-session")
async def create_chaster_session(payload: ChasterCreateSessionRequest, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if payload.min_duration_minutes > payload.max_duration_minutes:
        raise HTTPException(status_code=400, detail="min_duration_minutes must be <= max_duration_minutes.")
    if payload.min_limit_duration_minutes > payload.max_limit_duration_minutes:
        raise HTTPException(status_code=400, detail="min_limit_duration_minutes must be <= max_limit_duration_minutes.")
    effective_code = str(payload.code or "").strip() or _nine_digit_code()

    base_url = str(getattr(request.app.state.config, "CHASTER_API_BASE", "https://api.chaster.app") or "").strip()
    base_url = base_url.rstrip("/")
    if not base_url:
        raise HTTPException(status_code=400, detail="Chaster API base URL is empty.")

    create_code_payload = dict(payload.create_code_payload or {})
    if not create_code_payload:
        create_code_payload = {"code": effective_code}
    elif "code" not in create_code_payload:
        create_code_payload["code"] = effective_code

    code_rep = await _post_json(
        f"{base_url}/combinations/code",
        payload.chaster_api_token.strip(),
        create_code_payload,
    )
    combination_id = _extract_first_value(code_rep, {"id", "_id", "combinationId", "combination_id", "codeId", "code_id"})
    if not combination_id:
        raise HTTPException(status_code=400, detail="Unable to resolve combination id from Chaster response.")

    create_lock_payload = dict(payload.create_lock_payload or {})
    if not create_lock_payload:
        min_duration_seconds = int(payload.min_duration_minutes) * 60
        max_duration_seconds = int(payload.max_duration_minutes) * 60
        min_limit_minutes = int(payload.min_limit_duration_minutes)
        max_limit_minutes = int(payload.max_limit_duration_minutes)
        if bool(payload.limit_lock_time):
            if min_limit_minutes <= 0:
                min_limit_minutes = int(payload.min_duration_minutes)
            if max_limit_minutes <= 0:
                max_limit_minutes = int(payload.max_duration_minutes)
            if max_limit_minutes < min_limit_minutes:
                max_limit_minutes = min_limit_minutes
        min_limit_duration_seconds = max(0, min_limit_minutes) * 60
        max_limit_duration_seconds = max(0, max_limit_minutes) * 60
        base_payload = {
            "combinationId": combination_id,
            "minDuration": min_duration_seconds,
            "maxDuration": max_duration_seconds,
            "displayRemainingTime": bool(payload.display_remaining_time),
            "allowSessionOffer": bool(payload.allow_session_offer),
            "isTestLock": bool(payload.is_test_lock),
            "hideTimeLogs": bool(payload.hide_time_logs),
            "extensions": _sanitize_extensions(payload.extensions),
        }
        if bool(payload.limit_lock_time):
            base_payload["limitLockTime"] = True
            base_payload["minLimitDuration"] = min_limit_duration_seconds
            base_payload["maxLimitDuration"] = max_limit_duration_seconds
        else:
            base_payload["limitLockTime"] = False
        if payload.extensions:
            base_payload["extensions"] = _sanitize_extensions(payload.extensions)
        create_lock_payload = base_payload
    else:
        if "combinationId" not in create_lock_payload and "combination" not in create_lock_payload:
            create_lock_payload["combinationId"] = combination_id
        create_lock_payload.setdefault("displayRemainingTime", bool(payload.display_remaining_time))
        create_lock_payload.setdefault("limitLockTime", bool(payload.limit_lock_time))
        create_lock_payload.setdefault("allowSessionOffer", bool(payload.allow_session_offer))
        create_lock_payload.setdefault("isTestLock", bool(payload.is_test_lock))
        create_lock_payload.setdefault("hideTimeLogs", bool(payload.hide_time_logs))
        create_lock_payload["extensions"] = _sanitize_extensions(
            create_lock_payload.get("extensions") or payload.extensions or []
        )
        if bool(create_lock_payload.get("limitLockTime")):
            min_limit_minutes = int(payload.min_limit_duration_minutes or 0) or int(payload.min_duration_minutes)
            max_limit_minutes = int(payload.max_limit_duration_minutes or 0) or int(payload.max_duration_minutes)
            max_limit_minutes = max(min_limit_minutes, max_limit_minutes)
            create_lock_payload["minLimitDuration"] = min_limit_minutes * 60
            create_lock_payload["maxLimitDuration"] = max_limit_minutes * 60
        else:
            create_lock_payload.pop("minLimitDuration", None)
            create_lock_payload.pop("maxLimitDuration", None)
    lock_url = f"{base_url}/locks"
    lock_token = payload.chaster_api_token.strip()
    lock_rep: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = [dict(create_lock_payload)]
    # Fallback 1: normalize extension objects to the documented extension config shape.
    normalized_ext_payload = dict(create_lock_payload)
    normalized_ext_payload["extensions"] = _sanitize_extensions(create_lock_payload.get("extensions") or [])
    attempts.append(normalized_ext_payload)
    # Fallback 2: keep required booleans + provide an empty extensions array.
    no_extension_payload = dict(create_lock_payload)
    no_extension_payload["extensions"] = []
    attempts.append(no_extension_payload)
    # Fallback 3: strict minimal-but-schema-aware payload, while preserving lock-time constraints.
    minimal_payload = {
        "combinationId": combination_id,
        "minDuration": int(payload.min_duration_minutes) * 60,
        "maxDuration": int(payload.max_duration_minutes) * 60,
        "displayRemainingTime": bool(payload.display_remaining_time),
        "allowSessionOffer": bool(payload.allow_session_offer),
        "hideTimeLogs": bool(payload.hide_time_logs),
        "limitLockTime": bool(payload.limit_lock_time),
        "extensions": [],
    }
    if bool(payload.limit_lock_time):
        min_limit_minutes = int(payload.min_limit_duration_minutes or 0) or int(payload.min_duration_minutes)
        max_limit_minutes = int(payload.max_limit_duration_minutes or 0) or int(payload.max_duration_minutes)
        max_limit_minutes = max(min_limit_minutes, max_limit_minutes)
        minimal_payload["minLimitDuration"] = min_limit_minutes * 60
        minimal_payload["maxLimitDuration"] = max_limit_minutes * 60
    attempts.append(minimal_payload)
    last_exc: HTTPException | None = None
    attempt_errors: list[str] = []
    for idx, candidate in enumerate(attempts, start=1):
        try:
            lock_rep = await _post_json(lock_url, lock_token, candidate)
            create_lock_payload = candidate
            break
        except HTTPException as exc:
            last_exc = exc
            attempt_errors.append(
                f"attempt#{idx} payload={_compact_json_text(candidate)[:500]} error={str(exc.detail)}"
            )
            continue
    if lock_rep is None:
        details = " | ".join(attempt_errors)[:3500]
        if details:
            raise HTTPException(status_code=400, detail=f"Unable to create Chaster lock. {details}")
        raise last_exc or HTTPException(status_code=400, detail="Unable to create Chaster lock.")
    lock_id = _extract_first_value(lock_rep, {"id", "_id", "lockId", "lock_id", "publicLockId", "public_lock_id"})
    if not lock_id:
        raise HTTPException(status_code=400, detail="Unable to resolve lock id from Chaster response.")

    integration_config = {
        "api_base": base_url,
        "api_token": payload.chaster_api_token.strip(),
        "combination_id": combination_id,
        "lock_id": lock_id,
        "code": effective_code,
        "min_duration_minutes": int(payload.min_duration_minutes),
        "max_duration_minutes": int(payload.max_duration_minutes),
        "min_limit_duration_minutes": int(payload.min_limit_duration_minutes),
        "max_limit_duration_minutes": int(payload.max_limit_duration_minutes),
        "display_remaining_time": bool(payload.display_remaining_time),
        "limit_lock_time": bool(payload.limit_lock_time),
        "allow_session_offer": bool(payload.allow_session_offer),
        "is_test_lock": bool(payload.is_test_lock),
        "hide_time_logs": bool(payload.hide_time_logs),
        "extensions": list(create_lock_payload.get("extensions") or []),
        "created_at": datetime.now(UTC).isoformat(),
    }
    return {
        "success": True,
        "integration": "chaster",
        "integration_config": {"chaster": integration_config},
        "chaster": {
            "combination_id": combination_id,
            "lock_id": lock_id,
        },
    }
