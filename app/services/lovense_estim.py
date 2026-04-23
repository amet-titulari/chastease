"""Trigger Lovense toy stimulation on game events via the server-to-server Basic API.

Call ``trigger_lovense_game_event(event, run, db)`` from game handlers.
``event`` must be one of ``"continuous"``, ``"fail"``, ``"penalty"``, or ``"pass"``.

Event semantics:
  continuous – background pulse when a new step begins (makes the game harder)
  fail       – rule violation (movement detected, wrong pose submitted)
  penalty    – session extension applied
  pass       – success (pose confirmed, position held)

Requires:
  - Lovense to be enabled and configured in app settings
  - Player toy profile provider == "lovense" and enabled == True
  - ``lovense_game.enabled`` == True in player preferences
  - Toy connected via Lovense Connect app (server-to-server API needs active connection)
"""

import json
import logging

from sqlalchemy.orm import Session

from app.services.lovense import build_lovense_user_payload, lovense_status_payload, send_lovense_server_command

logger = logging.getLogger("uvicorn.error")

_LOVENSE_GAME_DEFAULTS: dict[str, dict] = {
    "continuous": {"intensity": 6,  "duration": 0},   # 0 = loop until next event
    "fail":       {"intensity": 18, "duration": 3},
    "penalty":    {"intensity": 20, "duration": 5},
    "pass":       {"intensity": 8,  "duration": 2},
}

_DEFAULT_LOVENSE_GAME_SETTINGS: dict = {
    "enabled": False,
    "intensity_continuous": 6,
    "duration_continuous": 0,
    "intensity_fail": 18,
    "duration_fail": 3,
    "intensity_penalty": 20,
    "duration_penalty": 5,
    "intensity_pass": 8,
    "duration_pass": 2,
}


def default_lovense_game_settings() -> dict:
    return dict(_DEFAULT_LOVENSE_GAME_SETTINGS)


def normalize_lovense_game_settings(raw: object) -> dict:
    source = raw if isinstance(raw, dict) else {}

    def _int(key: str, lo: int, hi: int, fallback: int) -> int:
        v = source.get(key)
        if v is None or v == "":
            return fallback
        try:
            return max(lo, min(hi, int(v)))
        except (ValueError, TypeError):
            return fallback

    def _bool(key: str, fallback: bool) -> bool:
        v = source.get(key)
        if v is None or v == "":
            return fallback
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in {"1", "true", "yes", "on"}

    return {
        "enabled": _bool("enabled", False),
        "intensity_continuous": _int("intensity_continuous", 0, 20, 6),
        "duration_continuous":  _int("duration_continuous",  0, 300, 0),
        "intensity_fail":       _int("intensity_fail",       0, 20, 18),
        "duration_fail":        _int("duration_fail",        0, 300, 3),
        "intensity_penalty":    _int("intensity_penalty",    0, 20, 20),
        "duration_penalty":     _int("duration_penalty",     0, 300, 5),
        "intensity_pass":       _int("intensity_pass",       0, 20, 8),
        "duration_pass":        _int("duration_pass",        0, 300, 2),
    }


def trigger_lovense_game_event(event: str, run, db: Session) -> None:
    """Load player settings from DB and fire the appropriate Lovense pulse.

    Silently does nothing when Lovense is disabled, not configured, player
    provider is not Lovense, game feedback is disabled, or the event name
    is unknown.
    """
    defaults = _LOVENSE_GAME_DEFAULTS.get(event)
    if defaults is None:
        logger.debug("Lovense estim: unknown event %r – skipped", event)
        return

    # Quick check: is Lovense globally enabled?
    status = lovense_status_payload()
    if not status.get("enabled"):
        return

    # Resolve player via: GameRun -> Session -> PlayerProfile -> AuthUser
    try:
        from app.models.session import Session as SessionModel
        from app.models.player_profile import PlayerProfile
        from app.models.auth_user import AuthUser

        session_obj = db.query(SessionModel).filter(SessionModel.id == run.session_id).first()
        if not session_obj:
            return
        player = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
        if not player:
            return
        user = db.query(AuthUser).filter(AuthUser.id == player.auth_user_id).first()
        if not user:
            return
    except Exception as exc:
        logger.warning("Lovense estim: DB lookup failed: %s", exc)
        return

    # Load preferences
    try:
        prefs = json.loads(player.preferences_json or "{}") or {}
    except Exception:
        prefs = {}

    # Check toy profile: must be lovense + enabled
    toys = prefs.get("toys") or {}
    if str(toys.get("provider", "none")).strip().lower() != "lovense":
        return
    if not bool(toys.get("enabled", False)):
        return

    # Check lovense_game settings
    game_cfg = normalize_lovense_game_settings(prefs.get("lovense_game") or {})
    if not game_cfg["enabled"]:
        return

    intensity = int(game_cfg.get(f"intensity_{event}", defaults["intensity"]) or 0)
    duration = int(game_cfg.get(f"duration_{event}", defaults["duration"]) or 0)

    if intensity <= 0:
        return

    uid = build_lovense_user_payload(user, player)["uid"]
    action = f"Vibrate:{intensity}"
    queued = send_lovense_server_command(uid, action, duration)
    if queued:
        logger.debug("Lovense estim: sent event=%r uid=%s intensity=%d duration=%d", event, uid, intensity, duration)
    else:
        logger.debug("Lovense estim: command not sent for event=%r (toy not connected?)", event)
