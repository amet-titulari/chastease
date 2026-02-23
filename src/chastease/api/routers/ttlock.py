import hashlib
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from chastease.api.setup_infra import resolve_user_id_from_token

router = APIRouter(prefix="/setup/ttlock", tags=["setup"])


class TTLockDiscoverRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    ttl_user: str = Field(min_length=1)
    ttl_pass: str | None = None
    ttl_pass_md5: str | None = None


async def _obtain_token(
    base_url: str,
    client_id: str,
    client_secret: str,
    username: str,
    password_md5: str,
) -> str:
    url = f"{base_url.rstrip('/')}/oauth2/token"
    data = {
        "grant_type": "password",
        "clientId": client_id,
        "clientSecret": client_secret,
        "username": username,
        "password": password_md5,
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = response.json()
    if payload.get("errcode", 0) not in (0, "0"):
        raise HTTPException(status_code=400, detail=f"TT-Lock auth failed: {payload.get('errmsg', 'unknown error')}")
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="TT-Lock auth returned no access_token.")
    return access_token


async def _list_locks(base_url: str, client_id: str, access_token: str) -> list[dict]:
    url = f"{base_url.rstrip('/')}/v3/lock/list"
    params = {
        "clientId": client_id,
        "accessToken": access_token,
        "pageNo": 1,
        "pageSize": 100,
        "date": int(time.time() * 1000),
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    if payload.get("errcode", 0) not in (0, "0"):
        raise HTTPException(status_code=400, detail=f"TT-Lock lock list failed: {payload.get('errmsg', 'unknown error')}")
    return payload.get("list", []) or []


async def _list_gateways(base_url: str, client_id: str, access_token: str) -> list[dict]:
    url = f"{base_url.rstrip('/')}/v3/gateway/list"
    params = {
        "clientId": client_id,
        "accessToken": access_token,
        "pageNo": 1,
        "pageSize": 100,
        "date": int(time.time() * 1000),
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    if payload.get("errcode", 0) not in (0, "0"):
        raise HTTPException(
            status_code=400,
            detail=f"TT-Lock gateway list failed: {payload.get('errmsg', 'unknown error')}",
        )
    return payload.get("list", []) or []


@router.post("/discover")
async def discover_ttlock_devices(payload: TTLockDiscoverRequest, request: Request) -> dict:
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    client_id = str(getattr(request.app.state.config, "TTL_CLIENT_ID", "") or "").strip()
    client_secret = str(getattr(request.app.state.config, "TTL_CLIENT_SECRET", "") or "").strip()
    base_url = str(getattr(request.app.state.config, "TTL_API_BASE", "https://euapi.ttlock.com") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="TT-Lock is not configured. Set TTL_CLIENT_ID and TTL_CLIENT_SECRET.",
        )

    password_md5 = str(payload.ttl_pass_md5 or "").strip().lower()
    if not password_md5:
        plain = str(payload.ttl_pass or "")
        if not plain:
            raise HTTPException(status_code=400, detail="ttl_pass or ttl_pass_md5 is required.")
        password_md5 = hashlib.md5(plain.encode("utf-8")).hexdigest()

    access_token = await _obtain_token(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        username=payload.ttl_user.strip(),
        password_md5=password_md5,
    )
    locks_raw = await _list_locks(base_url=base_url, client_id=client_id, access_token=access_token)
    gateways_raw = await _list_gateways(base_url=base_url, client_id=client_id, access_token=access_token)

    locks = [
        {
            "lockId": str(item.get("lockId") or ""),
            "lockAlias": str(item.get("lockAlias") or item.get("lockName") or item.get("lockId") or ""),
        }
        for item in locks_raw
        if item.get("lockId") is not None
    ]
    gateways = [
        {
            "gatewayId": str(item.get("gatewayId") or ""),
            "gatewayName": str(item.get("gatewayName") or item.get("gatewayId") or ""),
        }
        for item in gateways_raw
        if item.get("gatewayId") is not None
    ]

    return {"success": True, "locks": locks, "gateways": gateways, "ttl_pass_md5": password_md5}
