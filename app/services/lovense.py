import hashlib
import hmac
import logging

import httpx

from app.config import settings
from app.models.auth_user import AuthUser
from app.models.player_profile import PlayerProfile

logger = logging.getLogger("uvicorn.error")


class LovenseConfigError(RuntimeError):
    pass


class LovenseGatewayError(RuntimeError):
    pass


def lovense_status_payload() -> dict:
    platform = str(settings.lovense_platform or "").strip()
    simulator_enabled = bool(settings.lovense_simulator_enabled)
    effective_enabled = bool(settings.lovense_enabled or simulator_enabled)
    effective_configured = bool(simulator_enabled or (settings.lovense_enabled and platform and str(settings.lovense_developer_token or "").strip()))
    return {
        "enabled": effective_enabled,
        "configured": effective_configured,
        "simulator_enabled": simulator_enabled,
        "platform": platform,
        "app_type": _normalized_app_type(),
        "sdk_url": settings.lovense_sdk_url,
        "debug": bool(settings.lovense_debug),
    }


def _normalized_app_type() -> str:
    app_type = str(settings.lovense_app_type or "connect").strip().lower()
    if app_type not in {"connect", "remote"}:
        return "connect"
    return app_type


def _normalized_username(user: AuthUser, player: PlayerProfile | None = None) -> str:
    candidate = ""
    if player and str(player.nickname or "").strip():
        candidate = str(player.nickname).strip()
    elif str(user.username or "").strip():
        candidate = str(user.username).strip()
    elif str(user.email or "").strip():
        candidate = str(user.email).strip()
    if not candidate:
        candidate = f"user-{user.id}"
    return candidate[:64]


def build_lovense_user_payload(user: AuthUser, player: PlayerProfile | None = None) -> dict:
    uid = f"chastease-user-{int(user.id)}"
    uname = _normalized_username(user, player)
    secret = str(settings.secret_encryption_key or settings.admin_secret or settings.app_name).encode("utf-8")
    digest = hmac.new(secret, f"{uid}:{uname}".encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "uid": uid,
        "uname": uname,
        "utoken": digest,
    }


def request_lovense_auth_token(user: AuthUser, player: PlayerProfile | None = None) -> dict:
    status = lovense_status_payload()
    if not status["enabled"]:
        raise LovenseConfigError("Lovense integration is disabled.")
    if not status["configured"]:
        raise LovenseConfigError("Lovense integration is not fully configured.")

    user_payload = build_lovense_user_payload(user, player)
    request_payload = {
        "token": str(settings.lovense_developer_token or "").strip(),
        "uid": user_payload["uid"],
        "uname": user_payload["uname"],
        "utoken": user_payload["utoken"],
    }
    base_url = str(settings.lovense_api_base_url or "https://api.lovense-api.com/api/basicApi").rstrip("/")
    token_url = f"{base_url}/getToken"

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                token_url,
                headers={"Content-Type": "application/json"},
                json=request_payload,
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        raise LovenseGatewayError(f"Unable to contact Lovense API: {str(exc)[:240]}") from exc

    if not isinstance(payload, dict):
        raise LovenseGatewayError("Lovense API returned an invalid payload.")
    if int(payload.get("code") or 0) != 0:
        raise LovenseGatewayError(str(payload.get("message") or "Lovense API rejected the token request."))

    data = payload.get("data")
    auth_token = None
    if isinstance(data, dict):
        auth_token = data.get("authToken") or data.get("token")
    elif isinstance(data, str):
        auth_token = data
    auth_token = str(auth_token or "").strip()
    if not auth_token:
        raise LovenseGatewayError("Lovense API did not return an auth token.")

    return {
        **status,
        **user_payload,
        "auth_token": auth_token,
    }


def send_lovense_server_command(uid: str, action: str, time_sec: int) -> bool:
    """Send a command to a connected Lovense toy via the server-to-server Basic API.

    Requires the user to have their toy connected via Lovense Connect or Remote app.
    ``action`` format: ``"Vibrate:16"`` (command:intensity 0-20).
    ``time_sec``: duration in seconds; 0 means loop until stopped.
    Returns True if the API accepted the command.
    """
    token = str(settings.lovense_developer_token or "").strip()
    if not token or not uid:
        return False

    base_url = str(settings.lovense_api_base_url or "https://api.lovense-api.com/api/basicApi").rstrip("/")
    cmd_url = f"{base_url}/command"
    payload: dict = {
        "token": token,
        "uid": uid,
        "command": "Function",
        "action": action,
        "timeSec": time_sec,
        "stopPrevious": 1,
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(cmd_url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            code = int(data.get("code", 0))
            if code != 200:
                logger.debug("Lovense server command rejected: code=%s msg=%s", code, data.get("message"))
                return False
            return True
    except Exception as exc:
        logger.debug("Lovense server command failed: %s", exc)
        return False
