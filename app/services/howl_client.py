"""Howl Remote API client used for game-event E-Stim dispatch.

Howl API basics (per wiki):
- HTTP POST requests
- Bearer auth header
- Default port 4695
"""

from __future__ import annotations

import logging
import threading
import time

import httpx

logger = logging.getLogger("uvicorn.error")


def _normalize_base_url(base_url: str) -> str:
    raw = str(base_url or "").strip().rstrip("/")
    if not raw:
        return ""
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = f"http://{raw}"
    return raw


def _post(base_url: str, access_key: str, endpoint: str, payload: dict, timeout: float = 5.0) -> tuple[bool, object]:
    url = f"{_normalize_base_url(base_url)}{endpoint}"
    token = str(access_key or "").strip()
    if not url or not token:
        return False, "missing_url_or_access_key"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if not resp.is_success:
                return False, f"http_{resp.status_code}"
            try:
                return True, resp.json()
            except Exception:
                return True, {"ok": True}
    except Exception as exc:
        return False, str(exc)[:240]


def howl_status(base_url: str, access_key: str) -> dict:
    ok, payload = _post(base_url, access_key, "/status", {}, timeout=4.0)
    return {
        "running": bool(base_url and access_key),
        "connected": bool(ok),
        "url": _normalize_base_url(base_url),
        "api": "howl",
        "detail": payload if not ok else None,
    }


def _schedule_stop(base_url: str, access_key: str, seconds: float) -> None:
    def _worker() -> None:
        time.sleep(max(0.0, seconds))
        _post(base_url, access_key, "/stop_player", {}, timeout=4.0)

    t = threading.Thread(target=_worker, daemon=True, name="howl-stop-timer")
    t.start()


def send_howl_pulse(
    *,
    base_url: str,
    access_key: str,
    channel: str,
    intensity: int,
    ticks: int,
    activity: str,
) -> bool:
    """Send a short Howl pulse for one game event.

    Intensity maps 0..100 -> 0..200 (Howl power scale).
    Ticks map to 100 ms units.
    """
    base = _normalize_base_url(base_url)
    token = str(access_key or "").strip()
    if not base or not token:
        return False

    level = max(0, min(200, int(round(max(0, min(100, int(intensity))) * 2))))
    ch = str(channel or "A").strip().upper()

    set_payload: dict[str, int] = {}
    if ch == "A":
        set_payload["power_a"] = level
    elif ch == "B":
        set_payload["power_b"] = level
    else:
        set_payload["power_a"] = level
        set_payload["power_b"] = level

    ok_set, detail_set = _post(base, token, "/set_power", set_payload)
    if not ok_set:
        logger.debug("Howl pulse set_power failed: %s", detail_set)
        return False

    activity_name = str(activity or "").strip()
    started = False
    if activity_name:
        ok_load, _ = _post(base, token, "/load_activity", {"name": activity_name, "play": True})
        started = bool(ok_load)

    if not started:
        ok_start, detail_start = _post(base, token, "/start_player", {})
        if not ok_start:
            logger.debug("Howl pulse start_player failed: %s", detail_start)
            return False

    if ticks > 0:
        _schedule_stop(base, token, float(ticks) / 10.0)

    return True


def stop_howl_player(*, base_url: str, access_key: str) -> bool:
    """Best-effort stop command for an active Howl player."""
    ok, _ = _post(base_url, access_key, "/stop_player", {}, timeout=4.0)
    return bool(ok)
