from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
import os
import random
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from chastease.api.runtime import get_db_session
from chastease.api.setup_infra import resolve_user_id_from_token
from chastease.models import ChastitySession
from chastease.repositories.setup_store import load_sessions, save_sessions
from chastease.shared.secrets_crypto import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/setup/chaster", tags=["setup"])


class ChasterCreateSessionRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    chaster_api_token: str | None = None
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


class ChasterCheckSessionRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    chaster_api_token: str | None = None
    lock_id: str | None = None


class ChasterBindExtensionMainTokenRequest(BaseModel):
    main_token: str = Field(min_length=8)
    user_id: str | None = None
    auth_token: str | None = None


def _parse_iso_datetime(raw: Any) -> datetime | None:
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


def _latest_chaster_setup_entry(user_id: str) -> tuple[str | None, dict | None]:
    store = load_sessions()
    candidates: list[tuple[str, dict]] = []
    for setup_id, setup_session in store.items():
        if not isinstance(setup_session, dict):
            continue
        if str(setup_session.get("user_id") or "").strip() != user_id:
            continue
        if str(setup_session.get("status") or "").strip() not in {"draft", "setup_in_progress", "configured"}:
            continue
        candidates.append((setup_id, setup_session))
    if not candidates:
        return (None, None)
    candidates.sort(key=lambda item: str(item[1].get("updated_at") or item[1].get("created_at") or ""), reverse=True)
    return candidates[0]


def _persist_chaster_setup_config(user_id: str, chaster_cfg: dict[str, Any]) -> None:
    setup_id, setup_session = _latest_chaster_setup_entry(user_id)
    if not setup_id or not isinstance(setup_session, dict):
        return
    integration_config = (
        dict(setup_session.get("integration_config"))
        if isinstance(setup_session.get("integration_config"), dict)
        else {}
    )
    integration_config["chaster"] = chaster_cfg
    setup_session["integration_config"] = integration_config
    integrations = [str(item).strip().lower() for item in (setup_session.get("integrations") or []) if str(item).strip()]
    if "chaster" not in integrations:
        integrations.append("chaster")
    setup_session["integrations"] = integrations
    setup_session["updated_at"] = datetime.now(UTC).isoformat()
    store = load_sessions()
    store[setup_id] = setup_session
    save_sessions(store)


def _extract_extension_session_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    direct = str(payload.get("_id") or payload.get("id") or payload.get("sessionId") or payload.get("session_id") or "").strip()
    if direct:
        return direct
    for key in ("session", "data", "result", "item"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            resolved = _extract_extension_session_id(nested)
            if resolved:
                return resolved
    return ""


def _extract_extension_slug(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    direct = str(payload.get("extensionSlug") or payload.get("slug") or "").strip()
    if direct:
        return direct
    extension = payload.get("extension")
    if isinstance(extension, dict):
        nested = str(extension.get("slug") or extension.get("extensionSlug") or "").strip()
        if nested:
            return nested
    for key in ("session", "data", "result", "item"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            resolved = _extract_extension_slug(nested)
            if resolved:
                return resolved
    return ""


def _merge_chaster_extension_binding(
    chaster_cfg: dict[str, Any],
    session_payload: dict[str, Any],
    *,
    main_token: str | None = None,
    secret_key: str | None = None,
) -> dict[str, Any]:
    merged = dict(chaster_cfg or {})
    session_id = _extract_extension_session_id(session_payload)
    slug = _extract_extension_slug(session_payload)
    if session_id:
        merged["extension_session_id"] = session_id
    if slug:
        merged["extension_slug"] = slug
    merged["extension_main_page_bound_at"] = datetime.now(UTC).isoformat()
    merged["extension_session_snapshot"] = {
        "id": session_id or None,
        "lock_id": None,
        "slug": slug or None,
    }
    main_token_text = str(main_token or "").strip()
    if main_token_text and secret_key:
        merged["extension_main_token_enc"] = encrypt_secret(main_token_text, secret_key)
    return merged


def _collect_extension_session_candidates(payload: Any) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        ordered.append(text)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in ("sessionId", "session_id", "_id", "id"):
                add(node.get(key))
            for nested in node.values():
                walk(nested)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return ordered


def _bind_extension_session_in_setup_store(
    *,
    user_id: str | None,
    lock_id: str,
    session_payload: dict[str, Any],
    main_token: str | None,
    secret_key: str,
) -> int:
    target_lock_id = str(lock_id or "").strip()
    if not target_lock_id:
        return 0
    store = load_sessions()
    updated = 0
    changed = False
    for setup_id, setup_session in store.items():
        if not isinstance(setup_session, dict):
            continue
        if user_id and str(setup_session.get("user_id") or "").strip() != user_id:
            continue
        integration_config = setup_session.get("integration_config") if isinstance(setup_session.get("integration_config"), dict) else {}
        chaster_cfg = integration_config.get("chaster") if isinstance(integration_config.get("chaster"), dict) else {}
        if str(chaster_cfg.get("lock_id") or "").strip() != target_lock_id:
            continue
        integration_config = dict(integration_config)
        merged_chaster = _merge_chaster_extension_binding(
            chaster_cfg,
            session_payload,
            main_token=main_token,
            secret_key=secret_key,
        )
        merged_chaster["extension_session_snapshot"]["lock_id"] = target_lock_id
        integration_config["chaster"] = merged_chaster
        setup_session["integration_config"] = integration_config
        if isinstance(setup_session.get("policy_preview"), dict):
            setup_session["policy_preview"]["integration_config"] = integration_config
        setup_session["updated_at"] = datetime.now(UTC).isoformat()
        store[setup_id] = setup_session
        updated += 1
        changed = True
    if changed:
        save_sessions(store)
    return updated


def _bind_extension_session_in_active_sessions(
    *,
    request: Request,
    user_id: str | None,
    lock_id: str,
    session_payload: dict[str, Any],
    main_token: str | None,
    secret_key: str,
) -> int:
    target_lock_id = str(lock_id or "").strip()
    if not target_lock_id:
        return 0
    db = get_db_session(request)
    updated = 0
    try:
        stmt = select(ChastitySession)
        if user_id:
            stmt = stmt.where(ChastitySession.user_id == user_id)
        sessions = db.scalars(stmt).all()
        for session in sessions:
            try:
                policy = json.loads(session.policy_snapshot_json or "{}")
            except Exception:
                continue
            if not isinstance(policy, dict):
                continue
            integration_config = policy.get("integration_config") if isinstance(policy.get("integration_config"), dict) else {}
            chaster_cfg = integration_config.get("chaster") if isinstance(integration_config.get("chaster"), dict) else {}
            if str(chaster_cfg.get("lock_id") or "").strip() != target_lock_id:
                continue
            integration_config = dict(integration_config)
            merged_chaster = _merge_chaster_extension_binding(
                chaster_cfg,
                session_payload,
                main_token=main_token,
                secret_key=secret_key,
            )
            merged_chaster["extension_session_snapshot"]["lock_id"] = target_lock_id
            integration_config["chaster"] = merged_chaster
            policy["integration_config"] = integration_config
            session.policy_snapshot_json = json.dumps(policy)
            session.updated_at = datetime.now(UTC)
            db.add(session)
            updated += 1
        if updated:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()
    return updated


def normalize_chaster_config(chaster_cfg: dict[str, Any] | None, secret_key: str) -> dict[str, Any]:
    cfg = dict(chaster_cfg or {})
    auth = dict(cfg.get("auth") or {}) if isinstance(cfg.get("auth"), dict) else {}
    mode = str(auth.get("mode") or "").strip()
    if not mode:
        mode = "legacy_token" if str(cfg.get("api_token") or "").strip() else ""
    if mode == "legacy_token":
        legacy_plain = str(cfg.get("api_token") or "").strip()
        if legacy_plain and not str(auth.get("access_token_enc") or "").strip():
            auth["access_token_enc"] = encrypt_secret(legacy_plain, secret_key)
        auth.setdefault("provider", "chaster")
        auth["mode"] = "legacy_token"
        cfg["auth"] = auth
    elif mode == "oauth2":
        access_plain = str(auth.get("access_token") or "").strip()
        refresh_plain = str(auth.get("refresh_token") or "").strip()
        if access_plain and not str(auth.get("access_token_enc") or "").strip():
            auth["access_token_enc"] = encrypt_secret(access_plain, secret_key)
            auth.pop("access_token", None)
        if refresh_plain and not str(auth.get("refresh_token_enc") or "").strip():
            auth["refresh_token_enc"] = encrypt_secret(refresh_plain, secret_key)
            auth.pop("refresh_token", None)
        auth.setdefault("provider", "chaster")
        auth["mode"] = "oauth2"
        cfg["auth"] = auth
    cfg["schema_version"] = int(cfg.get("schema_version") or 2)
    return cfg


def chaster_has_any_credentials(chaster_cfg: dict[str, Any] | None) -> bool:
    cfg = chaster_cfg if isinstance(chaster_cfg, dict) else {}
    if str(cfg.get("api_token") or "").strip():
        return True
    auth = cfg.get("auth") if isinstance(cfg.get("auth"), dict) else {}
    if not isinstance(auth, dict):
        return False
    if str(auth.get("access_token_enc") or "").strip():
        return True
    if str(auth.get("refresh_token_enc") or "").strip():
        return True
    return False


async def _refresh_oauth_tokens(chaster_cfg: dict[str, Any], request: Request) -> dict[str, Any]:
    cfg = normalize_chaster_config(chaster_cfg, request.app.state.config.SECRET_KEY)
    auth = dict(cfg.get("auth") or {})
    refresh_token_enc = str(auth.get("refresh_token_enc") or "").strip()
    if not refresh_token_enc:
        raise HTTPException(status_code=401, detail="Missing Chaster OAuth refresh token.")
    try:
        refresh_token = decrypt_secret(refresh_token_enc, request.app.state.config.SECRET_KEY)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Chaster OAuth refresh token format.") from exc

    token_url = str(getattr(request.app.state.config, "CHASTER_OAUTH_TOKEN_URL", "") or "").strip()
    client_id = str(getattr(request.app.state.config, "CHASTER_OAUTH_CLIENT_ID", "") or "").strip()
    client_secret = str(getattr(request.app.state.config, "CHASTER_OAUTH_CLIENT_SECRET", "") or "").strip()
    redirect_uri = str(getattr(request.app.state.config, "CHASTER_OAUTH_REDIRECT_URI", "") or "").strip()
    if not token_url or not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="Chaster OAuth is not fully configured on the server.")

    form_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
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
            detail=f"Chaster OAuth refresh failed with HTTP {response.status_code}: {response.text[:500]}",
        )
    try:
        token_payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Chaster OAuth refresh returned non-JSON response.") from exc
    if not isinstance(token_payload, dict):
        raise HTTPException(status_code=401, detail="Chaster OAuth refresh returned invalid payload.")
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Chaster OAuth refresh response missing access_token.")

    refresh_token_new = str(token_payload.get("refresh_token") or "").strip() or refresh_token
    expires_in = token_payload.get("expires_in")
    try:
        expires_in_seconds = max(60, int(expires_in))
    except Exception:
        expires_in_seconds = 3600
    expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in_seconds)).isoformat()

    auth["mode"] = "oauth2"
    auth["provider"] = "chaster"
    auth["access_token_enc"] = encrypt_secret(access_token, request.app.state.config.SECRET_KEY)
    auth["refresh_token_enc"] = encrypt_secret(refresh_token_new, request.app.state.config.SECRET_KEY)
    auth["token_type"] = str(token_payload.get("token_type") or auth.get("token_type") or "Bearer")
    auth["scope"] = str(token_payload.get("scope") or auth.get("scope") or "").strip()
    auth["expires_at"] = expires_at
    cfg["auth"] = auth
    cfg.pop("api_token", None)
    cfg["updated_at"] = datetime.now(UTC).isoformat()
    return cfg


async def resolve_chaster_api_token_async(
    chaster_cfg: dict[str, Any] | None,
    request: Request,
    *,
    allow_refresh: bool = True,
) -> tuple[str | None, dict[str, Any]]:
    cfg = normalize_chaster_config(chaster_cfg, request.app.state.config.SECRET_KEY)
    legacy_token = str(cfg.get("api_token") or "").strip()
    if legacy_token:
        return legacy_token, cfg

    auth = dict(cfg.get("auth") or {}) if isinstance(cfg.get("auth"), dict) else {}
    mode = str(auth.get("mode") or "").strip().lower()
    if mode == "legacy_token":
        access_token_enc = str(auth.get("access_token_enc") or "").strip()
        if not access_token_enc:
            return None, cfg
        try:
            return decrypt_secret(access_token_enc, request.app.state.config.SECRET_KEY), cfg
        except Exception:
            return None, cfg

    if mode != "oauth2":
        return None, cfg

    access_token_enc = str(auth.get("access_token_enc") or "").strip()
    expires_at = _parse_iso_datetime(auth.get("expires_at"))
    if access_token_enc and expires_at and expires_at > (datetime.now(UTC) + timedelta(seconds=30)):
        try:
            return decrypt_secret(access_token_enc, request.app.state.config.SECRET_KEY), cfg
        except Exception:
            pass
    if access_token_enc and expires_at is None:
        try:
            return decrypt_secret(access_token_enc, request.app.state.config.SECRET_KEY), cfg
        except Exception:
            pass
    if not allow_refresh:
        return None, cfg
    refreshed = await _refresh_oauth_tokens(cfg, request)
    refreshed_auth = dict(refreshed.get("auth") or {})
    refreshed_token_enc = str(refreshed_auth.get("access_token_enc") or "").strip()
    if not refreshed_token_enc:
        return None, refreshed
    try:
        token = decrypt_secret(refreshed_token_enc, request.app.state.config.SECRET_KEY)
    except Exception:
        return None, refreshed
    return token, refreshed


def resolve_chaster_api_token(
    chaster_cfg: dict[str, Any] | None,
    request: Request,
    *,
    allow_refresh: bool = True,
) -> tuple[str | None, dict[str, Any]]:
    return asyncio.run(resolve_chaster_api_token_async(chaster_cfg, request, allow_refresh=allow_refresh))


def _compact_json_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        try:
            import json
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
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
            except (ValueError, KeyError):
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


async def _get_json(url: str, token: str) -> Any:
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    last_detail = ""
    for attempt in range(1, 3):
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            transaction_id = str(response.headers.get("x-chaster-transaction-id") or "").strip()
            retry_after_raw = str(response.headers.get("retry-after") or "").strip()
            retry_after = int(retry_after_raw) if retry_after_raw.isdigit() else 0
            body_text = response.text[:700].strip()
            last_detail = (
                f"Chaster API GET {url} failed with HTTP {response.status_code}"
                f"{(' (tx=' + transaction_id + ')') if transaction_id else ''}"
                f"{(': ' + body_text) if body_text else ''}"
            )
            should_retry = response.status_code >= 500 and retry_after > 0 and attempt < 2
            if should_retry:
                await asyncio.sleep(max(1, min(retry_after, 15)))
                continue
            raise HTTPException(status_code=400, detail=last_detail)
        try:
            return response.json()
        except Exception as exc:  # pragma: no cover - defensive branch
            raise HTTPException(status_code=400, detail=f"Chaster API returned non-JSON response for {url}.") from exc
    raise HTTPException(status_code=400, detail=last_detail or f"Chaster API GET {url} failed.")


def _developer_headers(request: Request) -> dict[str, str]:
    token = str(getattr(request.app.state.config, "CHASTER_DEVELOPER_TOKEN", "") or "").strip()
    if not token:
        raise HTTPException(status_code=500, detail="CHASTER_DEVELOPER_TOKEN is not configured.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _developer_api_base(request: Request) -> str:
    base = str(getattr(request.app.state.config, "CHASTER_DEVELOPER_API_BASE", "https://api.chaster.app/api") or "").strip()
    base = base.rstrip("/")
    if not base:
        raise HTTPException(status_code=500, detail="CHASTER_DEVELOPER_API_BASE is empty.")
    return base


def _extension_slug(request: Request) -> str:
    slug = str(getattr(request.app.state.config, "CHASTER_EXTENSION_SLUG", "") or "").strip()
    if not slug:
        raise HTTPException(status_code=500, detail="CHASTER_EXTENSION_SLUG is not configured.")
    return slug


def _extract_extension_lock_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("lock_id", "lockId", "_id", "id"):
        value = str(payload.get(key) or "").strip()
        if not value:
            continue
        if key in {"lock_id", "lockId"}:
            return value
        if any(marker in payload for marker in ("status", "startDate", "endDate", "combination", "title")):
            return value
    for key in ("lock", "session", "data", "item", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            resolved = _extract_extension_lock_id(nested)
            if resolved:
                return resolved
    return ""


def _find_extension_session_id(payload: Any, lock_id: str) -> str:
    normalized_lock_id = str(lock_id or "").strip()
    if not normalized_lock_id:
        return ""
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        if not isinstance(item, dict):
            continue
        item_lock_id = _extract_extension_lock_id(item)
        if item_lock_id == normalized_lock_id:
            session_id = str(item.get("_id") or item.get("id") or "").strip()
            if session_id:
                return session_id
        for key in ("results", "items", "data"):
            nested = item.get(key)
            if isinstance(nested, list):
                found = _find_extension_session_id(nested, normalized_lock_id)
                if found:
                    return found
    return ""


async def _resolve_extension_session_id(lock_id: str, request: Request) -> str | None:
    normalized_lock_id = str(lock_id or "").strip()
    if not normalized_lock_id:
        return None
    base_url = _developer_api_base(request)
    headers = _developer_headers(request)
    payload = {
        "extensionSlug": _extension_slug(request),
        "limit": 100,
    }
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{base_url}/extensions/sessions/search", headers=headers, json=payload)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Chaster extension session search failed with HTTP {response.status_code}: {response.text[:500]}",
        )
    try:
        response_json = response.json()
    except (ValueError, KeyError):
        response_json = {}
    return session_id or None


async def _resolve_extension_session_from_main_token(main_token: str, request: Request) -> dict[str, Any]:
    token = str(main_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="main_token is required.")
    base_url = _developer_api_base(request)
    headers = _developer_headers(request)
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    encoded_token = quote(token, safe="")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(f"{base_url}/extensions/auth/sessions/{encoded_token}", headers=headers)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Chaster extension main-token lookup failed with HTTP {response.status_code}: {response.text[:500]}",
        )
    try:
        payload = response.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Chaster extension main-token lookup returned non-JSON response.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Chaster extension main-token lookup returned invalid payload.")
    return payload


async def _resolve_verified_extension_session_id_from_main_token(main_token: str, request: Request) -> tuple[str, dict[str, Any]]:
    payload = await _resolve_extension_session_from_main_token(main_token, request)
    candidates = _collect_extension_session_candidates(payload)
    if not candidates:
        raise HTTPException(status_code=502, detail="Unable to resolve Chaster extension session id from mainToken.")

    base_url = _developer_api_base(request)
    headers = _developer_headers(request)
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for candidate in candidates:
            encoded = quote(candidate, safe="")
            response = await client.get(f"{base_url}/extensions/sessions/{encoded}", headers=headers)
            if response.status_code >= 400:
                continue
            try:
                verified_payload = response.json()
            except Exception:
                verified_payload = {}
            if not isinstance(verified_payload, dict):
                verified_payload = {}
            enriched_payload = dict(payload)
            enriched_payload["sessionId"] = candidate
            if verified_payload:
                enriched_payload["session"] = verified_payload
            return candidate, enriched_payload
    raise HTTPException(
        status_code=502,
        detail=(
            "Unable to verify Chaster extension session id from mainToken. "
            f"Tried candidates: {', '.join(candidates[:6])}"
        ),
    )


async def resolve_verified_extension_session_from_main_token(main_token: str, request: Request) -> tuple[str, dict[str, Any]]:
    return await _resolve_verified_extension_session_id_from_main_token(main_token, request)


def resolve_verified_extension_session_from_main_token_sync(main_token: str, request: Request) -> tuple[str, dict[str, Any]]:
    token = str(main_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="main_token is required.")
    base_url = _developer_api_base(request)
    headers = _developer_headers(request)
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    encoded_token = quote(token, safe="")
    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{base_url}/extensions/auth/sessions/{encoded_token}", headers=headers)
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Chaster extension main-token lookup failed with HTTP {response.status_code}: {response.text[:500]}",
            )
        try:
            payload = response.json()
        except (ValueError, KeyError):
            raise HTTPException(status_code=502, detail="Chaster extension main-token lookup returned non-JSON response.")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Chaster extension main-token lookup returned invalid payload.")

        candidates = _collect_extension_session_candidates(payload)
        if not candidates:
            raise HTTPException(status_code=502, detail="Unable to resolve Chaster extension session id from mainToken.")
        for candidate in candidates:
            encoded = quote(candidate, safe="")
            verify_response = client.get(f"{base_url}/extensions/sessions/{encoded}", headers=headers)
            if verify_response.status_code >= 400:
                continue
            try:
                verified_payload = verify_response.json()
            except (ValueError, KeyError):
                verified_payload = {}
            if not isinstance(verified_payload, dict):
                verified_payload = {}
            enriched_payload = dict(payload)
            enriched_payload["sessionId"] = candidate
            if verified_payload:
                enriched_payload["session"] = verified_payload
            return candidate, enriched_payload
    raise HTTPException(
        status_code=502,
        detail=(
            "Unable to verify Chaster extension session id from mainToken. "
            f"Tried candidates: {', '.join(candidates[:6])}"
        ),
    )


async def _request_ok(
    *,
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(method.upper(), url, headers=headers, json=payload)
    if response.status_code >= 400:
        transaction_id = str(response.headers.get("x-chaster-transaction-id") or "").strip()
        body_text = response.text[:700].strip()
        detail = (
            f"Chaster API {method.upper()} {url} failed with HTTP {response.status_code}"
            f"{(' (tx=' + transaction_id + ')') if transaction_id else ''}"
            f"{(': ' + body_text) if body_text else ''}"
        )
        raise HTTPException(status_code=400, detail=detail)
    if not response.text.strip():
        return None
    try:
        parsed = response.json()
    except (ValueError, KeyError):
        return {"raw_response": response.text[:700]}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


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


def _extract_first_number(obj: Any, keys: set[str]) -> int | None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys:
                try:
                    return int(value)
                except Exception:
                    pass
        for value in obj.values():
            nested = _extract_first_number(value, keys)
            if nested is not None:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = _extract_first_number(item, keys)
            if nested is not None:
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


def _extract_lock_candidates(payload: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            keys = set(node.keys())
            if keys & {
                "id",
                "_id",
                "lockId",
                "lock_id",
                "publicLockId",
                "public_lock_id",
                "status",
                "state",
                "isLocked",
                "locked",
                "isActive",
                "active",
            }:
                results.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return results


def _lock_looks_active(lock_data: dict[str, Any]) -> bool:
    true_flags = {"isLocked", "locked", "isActive", "active", "isRunning", "running", "inProgress", "ongoing"}
    for key in true_flags:
        value = lock_data.get(key)
        if value is True:
            return True

    status_keys = {"status", "state", "lockStatus", "lock_status"}
    active_states = {"active", "locked", "running", "in_progress", "ongoing", "started"}
    for key in status_keys:
        raw = lock_data.get(key)
        if raw is None:
            continue
        normalized = str(raw).strip().lower()
        if normalized in active_states:
            return True

    for key in ("remainingSeconds", "remaining_seconds"):
        raw = lock_data.get(key)
        try:
            if int(raw) > 0:
                return True
        except Exception:
            continue

    return False


def _parse_datetime_candidate(raw: Any) -> datetime | None:
    if raw is None:
        return None
    # Epoch seconds / milliseconds
    if isinstance(raw, (int, float)):
        value = float(raw)
        if value > 10_000_000_000:
            value = value / 1000.0
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except Exception:
            return None

    text = str(raw).strip()
    if not text:
        return None
    # Numeric timestamp in string form
    if text.isdigit():
        try:
            value = float(text)
            if value > 10_000_000_000:
                value = value / 1000.0
            return datetime.fromtimestamp(value, tz=UTC)
        except Exception:
            return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_lock_runtime(lock_data: dict[str, Any]) -> tuple[int | None, str | None]:
    remaining_keys = {
        "remainingSeconds",
        "remaining_seconds",
        "remainingTime",
        "remaining_time",
        "timeLeft",
        "time_left",
        "durationRemaining",
        "duration_remaining",
    }
    remaining_seconds = _extract_first_number(lock_data, remaining_keys)
    if isinstance(remaining_seconds, int):
        remaining_seconds = max(0, remaining_seconds)

    target_keys = {
        "endAt",
        "end_at",
        "endsAt",
        "ends_at",
        "endDate",
        "end_date",
        "unlockAt",
        "unlock_at",
        "unlockDate",
        "unlock_date",
    }
    target_end_at: str | None = None
    for key in target_keys:
        value = lock_data.get(key)
        parsed = _parse_datetime_candidate(value)
        if parsed is not None:
            target_end_at = parsed.isoformat()
            break
    if target_end_at is None:
        # fallback: search nested structures
        for candidate in _extract_lock_candidates(lock_data):
            for key in target_keys:
                value = candidate.get(key)
                parsed = _parse_datetime_candidate(value)
                if parsed is not None:
                    target_end_at = parsed.isoformat()
                    break
            if target_end_at is not None:
                break

    return remaining_seconds, target_end_at


async def fetch_chaster_lock_runtime(
    *,
    api_base: str,
    api_token: str | None,
    lock_id: str,
) -> dict[str, Any]:
    base_url = str(api_base or "https://api.chaster.app").strip().rstrip("/")
    token = str(api_token or "").strip()
    target_lock_id = str(lock_id or "").strip()
    if not token:
        return {"success": False, "has_active_session": False, "lock_id": target_lock_id or None, "check_error": "Missing Chaster API token."}
    if not target_lock_id:
        return {"success": False, "has_active_session": False, "lock_id": None, "check_error": "Missing Chaster lock_id."}

    probe_errors: list[str] = []
    candidates: list[dict[str, Any]] = []

    try:
        lock_payload = await _get_json(f"{base_url}/locks/{target_lock_id}", token)
        if isinstance(lock_payload, dict):
            candidates.append(lock_payload)
    except HTTPException as exc:
        probe_errors.append(str(exc.detail))

    try:
        list_payload = await _get_json(f"{base_url}/locks", token)
        list_candidates = _extract_lock_candidates(list_payload)
        matched = []
        for item in list_candidates:
            found_lock_id = _extract_first_value(item, {"id", "_id", "lockId", "lock_id", "publicLockId", "public_lock_id"})
            if found_lock_id == target_lock_id:
                matched.append(item)
        candidates.extend(matched)
    except HTTPException as exc:
        probe_errors.append(str(exc.detail))

    if not candidates:
        return {
            "success": False if probe_errors else True,
            "has_active_session": False,
            "lock_id": target_lock_id,
            "remaining_seconds": None,
            "target_end_at": None,
            "raw_status": None,
            "can_be_unlocked": None,
            "is_ready_to_unlock": None,
            "reasons_preventing_unlocking": [],
            "check_error": " | ".join(probe_errors) if probe_errors else None,
        }

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if _lock_looks_active(candidate):
            found_lock_id = _extract_first_value(candidate, {"id", "_id", "lockId", "lock_id", "publicLockId", "public_lock_id"}) or target_lock_id
            remaining_seconds, target_end_at = _extract_lock_runtime(candidate)
            raw_status = str(
                candidate.get("status")
                or candidate.get("state")
                or candidate.get("lockStatus")
                or candidate.get("lock_status")
                or ""
            ).strip() or None
            reasons = candidate.get("reasonsPreventingUnlocking")
            if not isinstance(reasons, list):
                reasons = []
            return {
                "success": True,
                "has_active_session": True,
                "lock_id": found_lock_id,
                "remaining_seconds": remaining_seconds,
                "target_end_at": target_end_at,
                "raw_status": raw_status,
                "can_be_unlocked": (
                    bool(candidate.get("canBeUnlocked"))
                    if candidate.get("canBeUnlocked") is not None
                    else None
                ),
                "is_ready_to_unlock": (
                    bool(candidate.get("isReadyToUnlock"))
                    if candidate.get("isReadyToUnlock") is not None
                    else None
                ),
                "reasons_preventing_unlocking": [str(item).strip() for item in reasons if str(item).strip()],
                "check_error": None,
            }

    return {
        "success": True,
        "has_active_session": False,
        "lock_id": target_lock_id,
        "remaining_seconds": None,
        "target_end_at": None,
        "raw_status": None,
        "can_be_unlocked": None,
        "is_ready_to_unlock": None,
        "reasons_preventing_unlocking": [],
        "check_error": None,
    }


@router.post("/check-active-session")
async def check_active_chaster_session(payload: ChasterCheckSessionRequest, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    base_url = str(getattr(request.app.state.config, "CHASTER_API_BASE", "https://api.chaster.app") or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=400, detail="Chaster API base URL is empty.")

    supplied_token = str(payload.chaster_api_token or "").strip()
    checked_lock_id = str(payload.lock_id or "").strip()
    resolved_cfg: dict[str, Any] | None = None
    if not supplied_token or not checked_lock_id:
        _setup_id, setup_session = _latest_chaster_setup_entry(payload.user_id)
        if isinstance(setup_session, dict):
            integration_config = (
                setup_session.get("integration_config")
                if isinstance(setup_session.get("integration_config"), dict)
                else {}
            )
            candidate_cfg = (
                integration_config.get("chaster")
                if isinstance(integration_config.get("chaster"), dict)
                else {}
            )
            if isinstance(candidate_cfg, dict):
                resolved_cfg = candidate_cfg
                if not checked_lock_id:
                    checked_lock_id = str(candidate_cfg.get("lock_id") or "").strip()

    token_for_check = supplied_token
    if not token_for_check and isinstance(resolved_cfg, dict):
        token_for_check, updated_cfg = await resolve_chaster_api_token_async(resolved_cfg, request, allow_refresh=True)
        if updated_cfg != resolved_cfg:
            _persist_chaster_setup_config(payload.user_id, updated_cfg)
            resolved_cfg = updated_cfg

    runtime = await fetch_chaster_lock_runtime(
        api_base=base_url,
        api_token=token_for_check,
        lock_id=checked_lock_id,
    )
    runtime["checked_lock_id"] = checked_lock_id or None
    return runtime


@router.post("/create-session")
async def create_chaster_session(payload: ChasterCreateSessionRequest, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if payload.min_duration_minutes > payload.max_duration_minutes:
        raise HTTPException(status_code=400, detail="min_duration_minutes must be <= max_duration_minutes.")
    if payload.min_limit_duration_minutes > payload.max_limit_duration_minutes:
        raise HTTPException(status_code=400, detail="min_limit_duration_minutes must be <= max_limit_duration_minutes.")
    existing_cfg: dict[str, Any] = {}
    _setup_id, setup_session = _latest_chaster_setup_entry(payload.user_id)
    if isinstance(setup_session, dict):
        integration_config = (
            setup_session.get("integration_config")
            if isinstance(setup_session.get("integration_config"), dict)
            else {}
        )
        candidate_cfg = (
            integration_config.get("chaster")
            if isinstance(integration_config.get("chaster"), dict)
            else {}
        )
        if isinstance(candidate_cfg, dict):
            existing_cfg = candidate_cfg

    lock_token = str(payload.chaster_api_token or "").strip()
    resolved_cfg = dict(existing_cfg)
    if not lock_token:
        lock_token, resolved_cfg = await resolve_chaster_api_token_async(existing_cfg, request, allow_refresh=True)
        if resolved_cfg != existing_cfg:
            _persist_chaster_setup_config(payload.user_id, resolved_cfg)
            existing_cfg = dict(resolved_cfg)
    if not lock_token:
        raise HTTPException(status_code=400, detail="Chaster credentials are missing. Connect via OAuth or provide token.")

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
        lock_token,
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
    extension_session_id = await _resolve_extension_session_id(lock_id, request)
    integration_config = {
        "schema_version": 2,
        "api_base": base_url,
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
    if extension_session_id:
        integration_config["extension_session_id"] = extension_session_id
    if str(payload.chaster_api_token or "").strip():
        integration_config["api_token"] = lock_token
    elif isinstance(resolved_cfg.get("auth"), dict):
        integration_config["auth"] = dict(resolved_cfg.get("auth") or {})
    integration_config = normalize_chaster_config(integration_config, request.app.state.config.SECRET_KEY)
    return {
        "success": True,
        "integration": "chaster",
        "integration_config": {"chaster": integration_config},
        "chaster": {
            "combination_id": combination_id,
            "lock_id": lock_id,
            "extension_session_id": extension_session_id,
        },
    }


@router.post("/extension/main-page/bind")
async def bind_extension_main_page(payload: ChasterBindExtensionMainTokenRequest, request: Request) -> dict[str, Any]:
    narrowed_user_id = None
    if payload.user_id or payload.auth_token:
        supplied_user_id = str(payload.user_id or "").strip()
        supplied_auth_token = str(payload.auth_token or "").strip()
        if not supplied_user_id or not supplied_auth_token:
            raise HTTPException(status_code=400, detail="user_id and auth_token must both be provided together.")
        token_user_id = resolve_user_id_from_token(supplied_auth_token, request)
        if token_user_id != supplied_user_id:
            raise HTTPException(status_code=401, detail="Invalid auth token for user.")
        narrowed_user_id = supplied_user_id

    extension_session_id, session_payload = await _resolve_verified_extension_session_id_from_main_token(
        payload.main_token,
        request,
    )
    lock_id = _extract_extension_lock_id(session_payload)
    if not lock_id:
        raise HTTPException(status_code=502, detail="Unable to resolve Chaster lock_id from extension session.")

    matched_setup_sessions = _bind_extension_session_in_setup_store(
        user_id=narrowed_user_id,
        lock_id=lock_id,
        session_payload=session_payload,
        main_token=payload.main_token,
        secret_key=request.app.state.config.SECRET_KEY,
    )
    matched_active_sessions = _bind_extension_session_in_active_sessions(
        request=request,
        user_id=narrowed_user_id,
        lock_id=lock_id,
        session_payload=session_payload,
        main_token=payload.main_token,
        secret_key=request.app.state.config.SECRET_KEY,
    )
    extension_slug = _extract_extension_slug(session_payload) or None
    return {
        "success": True,
        "lock_id": lock_id,
        "extension_session_id": extension_session_id,
        "extension_slug": extension_slug,
        "matched_setup_sessions": matched_setup_sessions,
        "matched_active_sessions": matched_active_sessions,
        "session": {
            "id": extension_session_id,
            "lock_id": lock_id,
            "slug": extension_slug,
        },
    }
