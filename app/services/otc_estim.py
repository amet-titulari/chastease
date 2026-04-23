"""Dispatch game events to the OTC E-Stim device.

Call ``trigger_game_estim_event(event, db)`` from game handlers.
``event`` must be one of ``"fail"``, ``"penalty"``, ``"pass"``, or ``"continuous"``.

Event semantics (works for all game types):
  continuous – background pulse fired at every new step / game start
  fail       – rule violation (movement detected, wrong pose submitted)
  penalty    – session extension penalty
  pass       – success (pose confirmed, position held)
"""

import logging

from sqlalchemy.orm import Session

from app.models.otc_settings import OtcSettings
from app.services.otc_client import send_otc_command

logger = logging.getLogger("uvicorn.error")

_EVENT_FIELDS = {
    "continuous": ("intensity_continuous", "ticks_continuous", "pattern_continuous"),
    "fail": ("intensity_fail", "ticks_fail", "pattern_fail"),
    "penalty": ("intensity_penalty", "ticks_penalty", "pattern_penalty"),
    "pass": ("intensity_pass", "ticks_pass", "pattern_pass"),
}


def trigger_game_estim_event(event: str, db: Session) -> None:
    """Load settings from DB and fire the appropriate E-Stim pulse.

    Silently does nothing when OTC is disabled, not configured, or the
    event name is unknown.
    """
    fields = _EVENT_FIELDS.get(event)
    if fields is None:
        logger.debug("OTC estim: unknown event %r – skipped", event)
        return

    try:
        settings = (
            db.query(OtcSettings)
            .filter(OtcSettings.singleton_key == "default")
            .first()
        )
    except Exception as exc:
        logger.warning("OTC estim: DB read failed: %s", exc)
        return

    if settings is None or not settings.enabled:
        return

    url = str(settings.otc_url or "").strip()
    if not url:
        return

    intensity_field, ticks_field, pattern_field = fields
    intensity = int(getattr(settings, intensity_field, 0) or 0)
    ticks = int(getattr(settings, ticks_field, 0) or 0)
    pattern = str(getattr(settings, pattern_field, "经典") or "经典")
    channel = str(settings.channel or "A").strip().upper()

    if intensity <= 0:
        return
    # ticks == 0 means "use -1" (loop until next event) — only for continuous
    if ticks == 0 and event != "continuous":
        return
    effective_ticks = -1 if (event == "continuous" and ticks == 0) else ticks

    channels = ["A", "B"] if channel == "AB" else [channel or "A"]
    for ch in channels:
        cmd = {
            "cmd": "set_pattern",
            "channel": ch,
            "pattern_name": pattern,
            "intensity": intensity,
            "ticks": effective_ticks,
        }
        queued = send_otc_command(cmd)
        if not queued:
            logger.debug("OTC estim: client not running, event=%r dropped", event)
            return
        logger.debug("OTC estim: queued event=%r channel=%s intensity=%d ticks=%d", event, ch, intensity, ticks)
