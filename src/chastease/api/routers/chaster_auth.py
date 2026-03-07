from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from chastease.api.runtime import (
    find_or_create_draft_setup_session,
    get_db_session,
    mint_auth_token,
    persist_auth_token,
    resolve_user_id_from_token,
)
from chastease.api.setup_infra import sync_setup_snapshot_to_active_session
from chastease.api.routers.chaster import normalize_chaster_config, resolve_chaster_api_token_async
from chastease.models import ExternalIdentity, User
from chastease.repositories.setup_store import load_sessions, save_sessions
from chastease.shared.secrets_crypto import encrypt_secret

router = APIRouter(prefix="/auth/chaster", tags=["auth"])


class ChasterOAuthRefreshRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)


class ChasterOAuthDisconnectRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _safe_return_to(value: str | None, fallback: str) -> str:
    target = str(value or "").strip()
    if not target:
        return fallback
    if not target.startswith("/"):
        return fallback
    if target.startswith("//"):
        return fallback
    return target


def _iso_to_date_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = _parse_iso(text)
    if parsed is None:
        return None
    return parsed.date().isoformat()


def _parse_iso(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_lock_id(lock_data: dict[str, Any]) -> str:
    for key in ("_id", "id", "lockId", "lock_id", "publicLockId", "public_lock_id"):
        value = str(lock_data.get(key) or "").strip()
        if value:
            return value
    return ""


def _seconds_to_minutes(raw: Any) -> int | None:
    try:
        value = int(raw)
    except Exception:
        return None
    if value < 0:
        return None
    return max(0, round(value / 60))


def _map_chaster_lock_into_setup_fields(setup_session: dict, chaster_cfg: dict[str, Any]) -> None:
    lock = chaster_cfg.get("lock") if isinstance(chaster_cfg.get("lock"), dict) else {}
    if not isinstance(lock, dict) or not lock:
        return

    start_date = _iso_to_date_text(lock.get("start_date"))
    min_end_date = _iso_to_date_text(lock.get("min_end_date"))
    max_end_date = _iso_to_date_text(lock.get("max_end_date"))
    end_date = _iso_to_date_text(lock.get("end_date"))

    status = str(setup_session.get("status") or "").strip()
    can_overwrite = status in {"draft", "setup_in_progress"}

    if start_date and (can_overwrite or not str(setup_session.get("contract_start_date") or "").strip()):
        setup_session["contract_start_date"] = start_date
    if min_end_date and (can_overwrite or not str(setup_session.get("contract_min_end_date") or "").strip()):
        setup_session["contract_min_end_date"] = min_end_date
    if max_end_date and (can_overwrite or not str(setup_session.get("contract_max_end_date") or "").strip()):
        setup_session["contract_max_end_date"] = max_end_date
    if end_date and (can_overwrite or not str(setup_session.get("contract_end_date") or "").strip()):
        setup_session["contract_end_date"] = end_date

    # Keep contract fields in policy preview synchronized if present.
    if isinstance(setup_session.get("policy_preview"), dict):
        contract = (
            setup_session["policy_preview"].get("contract")
            if isinstance(setup_session["policy_preview"].get("contract"), dict)
            else {}
        )
        if start_date and (can_overwrite or not str(contract.get("start_date") or "").strip()):
            contract["start_date"] = start_date
        if min_end_date and (can_overwrite or not str(contract.get("min_end_date") or "").strip()):
            contract["min_end_date"] = min_end_date
        if max_end_date and (can_overwrite or not str(contract.get("max_end_date") or "").strip()):
            contract["max_end_date"] = max_end_date
        if end_date and (can_overwrite or not str(contract.get("end_date") or "").strip()):
            contract["end_date"] = end_date
        setup_session["policy_preview"]["contract"] = contract


def _lock_is_active(lock_data: dict[str, Any]) -> bool:
    status = str(lock_data.get("status") or lock_data.get("state") or "").strip().lower()
    if status in {"locked", "active", "running", "ongoing", "in_progress"}:
        return True
    for key in ("isLocked", "locked", "isActive", "active", "running"):
        if lock_data.get(key) is True:
            return True
    end_at = _parse_iso(lock_data.get("endDate") or lock_data.get("endAt") or lock_data.get("unlockAt"))
    if end_at is not None and end_at > datetime.now(UTC):
        return True
    return False


async def _enrich_chaster_cfg_with_live_data(
    access_token: str,
    chaster_cfg: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    base_url = str(getattr(request.app.state.config, "CHASTER_API_BASE", "https://api.chaster.app") or "").strip().rstrip("/")
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    locks: list[dict[str, Any]] = []
    check_error: str | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(f"{base_url}/locks", headers=headers)
            if response.status_code < 400:
                payload = response.json()
                if isinstance(payload, list):
                    locks = [item for item in payload if isinstance(item, dict)]
                elif isinstance(payload, dict):
                    locks = [payload]
            else:
                check_error = f"locks_http_{response.status_code}"
        except Exception as exc:
            check_error = f"locks_error_{exc.__class__.__name__}"

    selected_lock: dict[str, Any] | None = None
    active_locks = [item for item in locks if _lock_is_active(item)]
    if active_locks:
        active_locks.sort(
            key=lambda item: str(item.get("updatedAt") or item.get("startDate") or item.get("createdAt") or ""),
            reverse=True,
        )
        selected_lock = active_locks[0]
    elif locks:
        locks.sort(
            key=lambda item: str(item.get("updatedAt") or item.get("startDate") or item.get("createdAt") or ""),
            reverse=True,
        )
        selected_lock = locks[0]

    cfg = dict(chaster_cfg)
    cfg["last_probe_at"] = datetime.now(UTC).isoformat()
    if check_error:
        cfg["last_probe_error"] = check_error
    if locks:
        cfg["locks_snapshot"] = {
            "count": len(locks),
            "active_count": len(active_locks),
            "last_read_at": datetime.now(UTC).isoformat(),
        }
    if selected_lock:
        lock_id = _extract_lock_id(selected_lock)
        combination_id = str(selected_lock.get("combination") or selected_lock.get("combinationId") or "").strip()
        lock_status = str(selected_lock.get("status") or selected_lock.get("state") or "").strip()
        limit_lock_time = bool(selected_lock.get("limitLockTime", True))
        max_date = str(selected_lock.get("maxDate") or "").strip() or None
        max_limit_date = str(selected_lock.get("maxLimitDate") or "").strip() or None
        effective_max_end_date = max_date
        # No upper bound if Chaster explicitly disables lock-time limiting and exposes no maxLimitDate.
        if limit_lock_time is False and not max_limit_date:
            effective_max_end_date = None
        lock_block = {
            "lock_id": lock_id or None,
            "combination_id": combination_id or None,
            "status": lock_status or None,
            "title": str(selected_lock.get("title") or "").strip() or None,
            "start_date": str(selected_lock.get("startDate") or "").strip() or None,
            "end_date": str(selected_lock.get("endDate") or "").strip() or None,
            "min_end_date": str(selected_lock.get("minDate") or "").strip() or None,
            "max_end_date": effective_max_end_date,
            "max_date": max_date,
            "max_limit_date": max_limit_date,
            "display_remaining_time": bool(selected_lock.get("displayRemainingTime", True)),
            "limit_lock_time": limit_lock_time,
            "allow_session_offer": bool(selected_lock.get("allowSessionOffer", True)),
            "is_test_lock": bool(selected_lock.get("isTestLock", False)),
            "hide_time_logs": bool(selected_lock.get("hideTimeLogs", False)),
            "trusted": bool(selected_lock.get("trusted", False)),
            "role": str(selected_lock.get("role") or "").strip() or None,
            "is_allowed_to_view_time": bool(selected_lock.get("isAllowedToViewTime", False)),
            "raw": selected_lock,
        }
        cfg["lock"] = lock_block
        if lock_id:
            cfg["lock_id"] = lock_id
        if combination_id:
            cfg["combination_id"] = combination_id
        cfg["display_remaining_time"] = lock_block["display_remaining_time"]
        cfg["limit_lock_time"] = lock_block["limit_lock_time"]
        cfg["allow_session_offer"] = lock_block["allow_session_offer"]
        cfg["is_test_lock"] = lock_block["is_test_lock"]
        cfg["hide_time_logs"] = lock_block["hide_time_logs"]
        if isinstance(selected_lock.get("extensions"), list):
            cfg["extensions"] = selected_lock.get("extensions")
        min_minutes = _seconds_to_minutes(selected_lock.get("minDuration"))
        max_minutes = _seconds_to_minutes(selected_lock.get("maxDuration"))
        min_limit_minutes = _seconds_to_minutes(selected_lock.get("minLimitDuration"))
        max_limit_minutes = _seconds_to_minutes(selected_lock.get("maxLimitDuration"))
        if min_minutes is not None:
            cfg["min_duration_minutes"] = min_minutes
        if max_minutes is not None:
            cfg["max_duration_minutes"] = max_minutes
        if min_limit_minutes is not None:
            cfg["min_limit_duration_minutes"] = min_limit_minutes
        if max_limit_minutes is not None:
            cfg["max_limit_duration_minutes"] = max_limit_minutes
        cfg["has_active_session"] = _lock_is_active(selected_lock)
    return normalize_chaster_config(cfg, request.app.state.config.SECRET_KEY)


def _mint_state(secret_key: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{_b64url_encode(raw)}.{_b64url_encode(sig)}"


def _verify_state(secret_key: str, state: str) -> dict[str, Any]:
    if "." not in state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")
    payload_part, sig_part = state.split(".", 1)
    try:
        payload_raw = _b64url_decode(payload_part)
        sig = _b64url_decode(sig_part)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state encoding.") from exc
    expected = hmac.new(secret_key.encode("utf-8"), payload_raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="Invalid OAuth state signature.")
    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state payload.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid OAuth state payload.")
    exp_raw = payload.get("exp")
    try:
        exp_ts = int(exp_raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state expiry.") from exc
    if int(datetime.now(UTC).timestamp()) > exp_ts:
        raise HTTPException(status_code=400, detail="OAuth state has expired.")
    return payload


def _latest_setup_session_for_user(user_id: str) -> tuple[str | None, dict | None]:
    store = load_sessions()
    candidates: list[tuple[str, dict]] = []
    for sid, sess in store.items():
        if not isinstance(sess, dict):
            continue
        if str(sess.get("user_id") or "").strip() != user_id:
            continue
        if str(sess.get("status") or "").strip() not in {"draft", "setup_in_progress", "configured"}:
            continue
        candidates.append((sid, sess))
    if not candidates:
        return (None, None)
    candidates.sort(key=lambda item: str(item[1].get("updated_at") or item[1].get("created_at") or ""), reverse=True)
    return candidates[0]


def _persist_chaster_config_for_user(
    user_id: str,
    chaster_cfg: dict[str, Any],
    request: Request,
    *,
    create_if_missing: bool = True,
) -> str | None:
    setup_id, setup_session = _latest_setup_session_for_user(user_id)
    if (setup_session is None or setup_id is None) and create_if_missing:
        setup_id, setup_session = find_or_create_draft_setup_session(user_id, "de")
        store = load_sessions()
        setup_session = store.get(setup_id) or setup_session
    if setup_session is None or setup_id is None:
        return None

    integration_config = (
        dict(setup_session.get("integration_config"))
        if isinstance(setup_session.get("integration_config"), dict)
        else {}
    )
    integration_config["chaster"] = chaster_cfg
    setup_session["integration_config"] = integration_config
    _map_chaster_lock_into_setup_fields(setup_session, chaster_cfg)
    integrations = [str(item).strip().lower() for item in (setup_session.get("integrations") or []) if str(item).strip()]
    if "chaster" not in integrations:
        integrations.append("chaster")
    setup_session["integrations"] = integrations
    if isinstance(setup_session.get("policy_preview"), dict):
        setup_session["policy_preview"]["integrations"] = integrations
        setup_session["policy_preview"]["integration_config"] = integration_config
    setup_session["updated_at"] = datetime.now(UTC).isoformat()
    store = load_sessions()
    store[setup_id] = setup_session
    save_sessions(store)
    sync_setup_snapshot_to_active_session(request, setup_session)
    return setup_id


async def _exchange_code_for_tokens(code: str, request: Request) -> dict[str, Any]:
    token_url = str(getattr(request.app.state.config, "CHASTER_OAUTH_TOKEN_URL", "") or "").strip()
    client_id = str(getattr(request.app.state.config, "CHASTER_OAUTH_CLIENT_ID", "") or "").strip()
    client_secret = str(getattr(request.app.state.config, "CHASTER_OAUTH_CLIENT_SECRET", "") or "").strip()
    redirect_uri = str(getattr(request.app.state.config, "CHASTER_OAUTH_REDIRECT_URI", "") or "").strip()
    if not token_url or not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="Chaster OAuth is not fully configured on the server.")

    form_data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(token_url, data=form_data, headers={"Accept": "application/json"})
    if response.status_code >= 400:
        raise HTTPException(
            status_code=401,
            detail=f"Chaster OAuth token exchange failed with HTTP {response.status_code}: {response.text[:600]}",
        )
    try:
        token_payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Chaster OAuth token exchange returned non-JSON response.") from exc
    if not isinstance(token_payload, dict):
        raise HTTPException(status_code=401, detail="Chaster OAuth token exchange returned invalid payload.")
    return token_payload


def _build_chaster_cfg_from_tokens(token_payload: dict[str, Any], request: Request) -> dict[str, Any]:
    access_token = str(token_payload.get("access_token") or "").strip()
    refresh_token = str(token_payload.get("refresh_token") or "").strip()
    token_type = str(token_payload.get("token_type") or "Bearer").strip()
    scope = str(token_payload.get("scope") or getattr(request.app.state.config, "CHASTER_OAUTH_SCOPES", "") or "").strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Chaster OAuth token exchange missing access_token.")
    expires_in = token_payload.get("expires_in")
    try:
        expires_seconds = max(60, int(expires_in))
    except Exception:
        expires_seconds = 3600

    cfg = {
        "schema_version": 2,
        "api_base": str(getattr(request.app.state.config, "CHASTER_API_BASE", "https://api.chaster.app") or "").strip(),
        "auth": {
            "mode": "oauth2",
            "provider": "chaster",
            "access_token_enc": encrypt_secret(access_token, request.app.state.config.SECRET_KEY),
            "refresh_token_enc": encrypt_secret(refresh_token, request.app.state.config.SECRET_KEY) if refresh_token else "",
            "token_type": token_type,
            "scope": scope,
            "expires_at": (datetime.now(UTC) + timedelta(seconds=expires_seconds)).isoformat(),
        },
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    return normalize_chaster_config(cfg, request.app.state.config.SECRET_KEY)


async def _fetch_chaster_identity(access_token: str, request: Request) -> dict[str, Any]:
    # Preferred path for OAuth login: resolve identity through OIDC userinfo.
    userinfo_url = str(getattr(request.app.state.config, "CHASTER_OAUTH_USERINFO_URL", "") or "").strip()
    if userinfo_url:
        timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(userinfo_url, headers=headers)
            if response.status_code < 400:
                payload = response.json()
                if isinstance(payload, dict):
                    sub = str(payload.get("sub") or payload.get("id") or payload.get("user_id") or "").strip()
                    if sub:
                        preferred = str(
                            payload.get("preferred_username")
                            or payload.get("name")
                            or payload.get("nickname")
                            or ""
                        ).strip()
                        return {
                            "chaster_user_id": sub,
                            "username": preferred or f"chaster-{sub[:8]}",
                            "raw": payload,
                        }
        except Exception:
            pass

    # Fallback path: try API profile/locks endpoints.
    base_url = str(getattr(request.app.state.config, "CHASTER_API_BASE", "https://api.chaster.app") or "").strip().rstrip("/")
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    user_candidates = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for path in ("/users/me", "/me", "/user", "/profile"):
            try:
                response = await client.get(f"{base_url}{path}", headers=headers)
            except Exception:
                continue
            if response.status_code >= 400:
                continue
            try:
                payload = response.json()
            except Exception:
                continue
            if isinstance(payload, dict):
                user_candidates.append(payload)
                break

        if not user_candidates:
            try:
                response = await client.get(f"{base_url}/locks", headers=headers)
                if response.status_code < 400:
                    payload = response.json()
                    if isinstance(payload, list):
                        for item in payload:
                            if not isinstance(item, dict):
                                continue
                            user_obj = item.get("user")
                            if isinstance(user_obj, dict):
                                user_candidates.append(user_obj)
                                break
            except Exception:
                pass

    if not user_candidates:
        # Last-resort fallback: parse JWT payload without verification to extract `sub`.
        try:
            parts = str(access_token).split(".")
            if len(parts) == 3:
                payload_raw = _b64url_decode(parts[1])
                payload = json.loads(payload_raw.decode("utf-8"))
                if isinstance(payload, dict):
                    sub = str(payload.get("sub") or "").strip()
                    if sub:
                        preferred = str(payload.get("preferred_username") or payload.get("name") or "").strip()
                        return {
                            "chaster_user_id": sub,
                            "username": preferred or f"chaster-{sub[:8]}",
                            "raw": payload,
                        }
        except Exception:
            pass
        raise HTTPException(
            status_code=400,
            detail="Unable to resolve Chaster user identity from OAuth token (userinfo/profile unavailable).",
        )
    user_obj = user_candidates[0]
    chaster_user_id = str(
        user_obj.get("_id")
        or user_obj.get("id")
        or user_obj.get("userId")
        or user_obj.get("user_id")
        or ""
    ).strip()
    if not chaster_user_id:
        raise HTTPException(status_code=400, detail="Chaster identity response did not include user id.")
    username = str(user_obj.get("username") or user_obj.get("name") or "").strip()
    return {"chaster_user_id": chaster_user_id, "username": username or f"chaster-{chaster_user_id[:8]}", "raw": user_obj}


def _resolve_or_create_user_from_chaster(identity: dict[str, Any], request: Request) -> User:
    provider = "chaster"
    external_user_id = str(identity.get("chaster_user_id") or "").strip()
    username = str(identity.get("username") or "").strip() or f"chaster-{external_user_id[:8]}"
    db = get_db_session(request)
    try:
        existing_identity = db.scalar(
            select(ExternalIdentity)
            .where(ExternalIdentity.provider == provider)
            .where(ExternalIdentity.external_user_id == external_user_id)
        )
        if existing_identity is not None:
            user = db.get(User, existing_identity.user_id)
            if user is None:
                raise HTTPException(status_code=500, detail="Broken external identity mapping.")
            user.display_name = username
            existing_identity.username = username
            existing_identity.metadata_json = json.dumps(identity.get("raw") or {})
            existing_identity.updated_at = datetime.now(UTC)
            db.add(user)
            db.add(existing_identity)
            db.commit()
            return user

        synthetic_email = f"chaster_{external_user_id}@oauth.local"
        already = db.scalar(select(User).where(User.email == synthetic_email))
        if already is not None:
            synthetic_email = f"chaster_{external_user_id}_{secrets.token_hex(3)}@oauth.local"

        user = User(
            id=str(uuid4()),
            email=synthetic_email,
            display_name=username,
            password_hash="",
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.flush()
        mapping = ExternalIdentity(
            id=str(uuid4()),
            user_id=user.id,
            provider=provider,
            external_user_id=external_user_id,
            username=username,
            metadata_json=json.dumps(identity.get("raw") or {}),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(mapping)
        db.commit()
        return user
    finally:
        db.close()


def _mint_local_auth_for_user(user_id: str, request: Request) -> str:
    ttl_days = int(getattr(request.app.state.config, "AUTH_TOKEN_TTL_DAYS", 30))
    token = mint_auth_token(user_id, request.app.state.config.SECRET_KEY)
    db = get_db_session(request)
    try:
        persist_auth_token(token, user_id, db, ttl_days)
    finally:
        db.close()
    return token


@router.get("/signin")
def chaster_oauth_signin(request: Request, return_to: str = "/app") -> RedirectResponse:
    if not bool(getattr(request.app.state.config, "AUTH_ENABLE_CHASTER_LOGIN", True)):
        raise HTTPException(status_code=404, detail="Not found.")
    authorize_url = str(getattr(request.app.state.config, "CHASTER_OAUTH_AUTHORIZE_URL", "") or "").strip()
    client_id = str(getattr(request.app.state.config, "CHASTER_OAUTH_CLIENT_ID", "") or "").strip()
    redirect_uri = str(getattr(request.app.state.config, "CHASTER_OAUTH_REDIRECT_URI", "") or "").strip()
    scopes = str(getattr(request.app.state.config, "CHASTER_OAUTH_SCOPES", "") or "").strip()
    if not authorize_url or not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Chaster OAuth is not fully configured on the server.")
    state_payload = {
        "mode": "signin",
        "return_to": _safe_return_to(return_to, "/app"),
        "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
        "nonce": secrets.token_hex(8),
    }
    state = _mint_state(request.app.state.config.SECRET_KEY, state_payload)
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if scopes:
        query["scope"] = scopes
    return RedirectResponse(url=f"{authorize_url}?{urlencode(query)}", status_code=302)


@router.get("/login")
def chaster_oauth_login(user_id: str, auth_token: str, request: Request, return_to: str = "/setup") -> RedirectResponse:
    token_user_id = resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    authorize_url = str(getattr(request.app.state.config, "CHASTER_OAUTH_AUTHORIZE_URL", "") or "").strip()
    client_id = str(getattr(request.app.state.config, "CHASTER_OAUTH_CLIENT_ID", "") or "").strip()
    redirect_uri = str(getattr(request.app.state.config, "CHASTER_OAUTH_REDIRECT_URI", "") or "").strip()
    scopes = str(getattr(request.app.state.config, "CHASTER_OAUTH_SCOPES", "") or "").strip()
    if not authorize_url or not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Chaster OAuth is not fully configured on the server.")

    state_payload = {
        "mode": "connect",
        "uid": user_id,
        "return_to": _safe_return_to(return_to, "/setup"),
        "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
        "nonce": secrets.token_hex(8),
    }
    state = _mint_state(request.app.state.config.SECRET_KEY, state_payload)
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if scopes:
        query["scope"] = scopes
    target = f"{authorize_url}?{urlencode(query)}"
    return RedirectResponse(url=target, status_code=302)


@router.get("/callback")
async def chaster_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    safe_state = _verify_state(request.app.state.config.SECRET_KEY, str(state or "").strip()) if state else {}
    mode = str(safe_state.get("mode") or "connect").strip().lower()
    return_to = _safe_return_to(
        safe_state.get("return_to"),
        "/app" if mode == "signin" else "/setup",
    )
    if error:
        msg = str(error_description or error).strip() or "oauth_error"
        params = urlencode({"chaster_oauth": "error", "message": msg})
        return RedirectResponse(url=f"{return_to}?{params}", status_code=302)
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    token_payload = await _exchange_code_for_tokens(code, request)
    chaster_cfg = _build_chaster_cfg_from_tokens(token_payload, request)
    if mode == "signin":
        access_token, _ = await resolve_chaster_api_token_async(chaster_cfg, request, allow_refresh=False)
        if not access_token:
            raise HTTPException(status_code=401, detail="Unable to resolve Chaster access token.")
        chaster_cfg = await _enrich_chaster_cfg_with_live_data(access_token, chaster_cfg, request)
        identity = await _fetch_chaster_identity(access_token, request)
        user = _resolve_or_create_user_from_chaster(identity, request)
        chaster_cfg["profile"] = {
            "chaster_user_id": str(identity.get("chaster_user_id") or "").strip() or None,
            "username": str(identity.get("username") or "").strip() or None,
            "last_read_at": datetime.now(UTC).isoformat(),
        }
        setup_id = _persist_chaster_config_for_user(user.id, chaster_cfg, request)
        auth_token = _mint_local_auth_for_user(user.id, request)
        query = urlencode(
            {
                "chaster_oauth": "ok",
                "user_id": user.id,
                "auth_token": auth_token,
                "display_name": user.display_name,
                "setup_session_id": setup_id,
            }
        )
        return RedirectResponse(url=f"{return_to}?{query}", status_code=302)

    user_id = str(safe_state.get("uid") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user in OAuth state.")
    access_token, _ = await resolve_chaster_api_token_async(chaster_cfg, request, allow_refresh=False)
    if access_token:
        chaster_cfg = await _enrich_chaster_cfg_with_live_data(access_token, chaster_cfg, request)
    setup_id = _persist_chaster_config_for_user(user_id, chaster_cfg, request)
    redirect_url = f"{return_to}?{urlencode({'setup_session_id': setup_id, 'chaster_oauth': 'ok'})}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/refresh")
async def chaster_oauth_refresh(payload: ChasterOAuthRefreshRequest, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    _setup_id, setup_session = _latest_setup_session_for_user(payload.user_id)
    if not isinstance(setup_session, dict):
        raise HTTPException(status_code=404, detail="No setup session found for user.")
    integration_config = (
        setup_session.get("integration_config")
        if isinstance(setup_session.get("integration_config"), dict)
        else {}
    )
    chaster_cfg = integration_config.get("chaster") if isinstance(integration_config.get("chaster"), dict) else {}
    if not isinstance(chaster_cfg, dict) or not chaster_cfg:
        raise HTTPException(status_code=404, detail="Chaster configuration not found.")
    _token, updated_cfg = await resolve_chaster_api_token_async(chaster_cfg, request, allow_refresh=True)
    _persist_chaster_config_for_user(payload.user_id, updated_cfg, request)
    auth = updated_cfg.get("auth") if isinstance(updated_cfg.get("auth"), dict) else {}
    return {
        "connected": True,
        "auth_mode": str(auth.get("mode") or ""),
        "expires_at": str(auth.get("expires_at") or "") or None,
        "has_refresh_token": bool(str(auth.get("refresh_token_enc") or "").strip()),
    }


@router.post("/disconnect")
def chaster_oauth_disconnect(payload: ChasterOAuthDisconnectRequest, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    _setup_id, setup_session = _latest_setup_session_for_user(payload.user_id)
    if not isinstance(setup_session, dict):
        raise HTTPException(status_code=404, detail="No setup session found for user.")
    integration_config = (
        dict(setup_session.get("integration_config"))
        if isinstance(setup_session.get("integration_config"), dict)
        else {}
    )
    chaster_cfg = dict(integration_config.get("chaster") or {}) if isinstance(integration_config.get("chaster"), dict) else {}
    chaster_cfg.pop("api_token", None)
    chaster_cfg.pop("auth", None)
    chaster_cfg["updated_at"] = datetime.now(UTC).isoformat()
    chaster_cfg = normalize_chaster_config(chaster_cfg, request.app.state.config.SECRET_KEY)
    _persist_chaster_config_for_user(payload.user_id, chaster_cfg, request)
    return {"disconnected": True}
