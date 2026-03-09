import base64
import copy
import json
import hashlib
import logging
import os
import random
import re
import time
import unicodedata
from pathlib import Path
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api.runtime import find_setup_session_id_for_active_session, get_db_session, lang, resolve_user_id_from_token
from chastease.api.routers.chaster import resolve_chaster_api_token, resolve_verified_extension_session_from_main_token_sync
from chastease.api.schemas import ChatActionExecuteRequest, ChatActionResolveRequest, ChatTurnRequest, ChatVisionReviewRequest
from chastease.models import AuditEntry, ChastitySession, Turn
from chastease.repositories.setup_store import load_sessions, save_sessions
from chastease.domains.roleplay import refresh_session_roleplay_state
from chastease.services.narration import extract_pending_actions, generate_ai_narration_for_session
from chastease.shared.secrets_crypto import decrypt_secret
from chastease.shared.audit import record_audit_event

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
    "freeze": "pause_timer",
    "unfreeze": "unpause_timer",
    "toggle_freeze": "pause_timer",
    "pause": "pause_timer",
    "pausetimer": "pause_timer",
    "freeze": "pause_timer",
    "freeze_timer": "pause_timer",
    "timer_pause": "pause_timer",
    "resume": "unpause_timer",
    "unpausetimer": "unpause_timer",
    "unfreeze": "unpause_timer",
    "resume_timer": "unpause_timer",
    "hygieneopen": "hygiene_open",
    "hygieneclose": "hygiene_close",
    "hygieneoeffnung": "hygiene_open",
    "hygiene_oeffnung": "hygiene_open",
    "hygieneöffnung": "hygiene_open",
    "hygieneschliessen": "hygiene_close",
    "hygiene_schliessen": "hygiene_close",
    "hygieneschließen": "hygiene_close",
    "hygiene_schließen": "hygiene_close",
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


def _normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _contains_word(text: str, candidate: str) -> bool:
    normalized_text = _normalize_text(text)
    normalized_candidate = _normalize_text(candidate)
    if not normalized_candidate:
        return False
    if " " in normalized_candidate:
        return normalized_candidate in normalized_text
    words = re.findall(r"\w+", normalized_text)
    return normalized_candidate in words


def _is_confirmation_message(message: str) -> bool:
    normalized = _normalize_text(message)
    tokens = {
        "ja",
        "yes",
        "ok",
        "okay",
        "bestaetige",
        "bestatige",
        "bestatigung",
        "confirm",
        "confirmed",
        "abbruch",
        "abbrechen",
        "beenden",
        "stop",
        "stopp",
        "notfall",
        "rot",
        "red",
        "abort",
        "weiter",
    }
    words = set(re.findall(r"\w+", normalized))
    return any(token in words for token in tokens)


def _is_abort_cancellation_message(message: str) -> bool:
    normalized = _normalize_text(message)
    cancellation_hints = (
        "nicht abbrechen",
        "kein abbruch",
        "abbruch nein",
        "false alarm",
        "fehlalarm",
        "entwarnung",
        "nicht mich",
        "not me",
        "betrifft nicht mich",
        "keine akute gefahr",
        "no acute danger",
    )
    return any(hint in normalized for hint in cancellation_hints)


def _extract_verification_status(narration: str) -> str | None:
    """Return normalized status from vision narration verdict (PASSED/FAILED)."""
    upper = str(narration or "").upper()
    if re.search(r"\bFAILED\b", upper) or re.search(r"\bNOT\s+PASSED\b", upper):
        return "failed"
    if re.search(r"\bPASSED\b", upper):
        return "success"
    return None


def _build_hygiene_open_pending_action(policy: dict, trigger: str, reason: str) -> dict:
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    opening_window_minutes = int(limits.get("opening_window_minutes") or 15)
    opening_window_minutes = max(1, min(opening_window_minutes, 240))
    seal_cfg = policy.get("seal") if isinstance(policy.get("seal"), dict) else {}
    seal_mode = str(seal_cfg.get("mode") or "none").strip().lower()
    if seal_mode not in {"none", "plomben", "versiegelung"}:
        seal_mode = "none"
    return {
        "action_type": "hygiene_open",
        "payload": {
            "reason": reason,
            "trigger": trigger,
            "opening_window_minutes": opening_window_minutes,
            "auto_relock_seconds": 5,
            "seal_mode": seal_mode,
            "seal_required_on_close": seal_mode in {"plomben", "versiegelung"},
        },
        "requires_execute_call": True,
    }


def _build_emergency_ttlock_open_pending_action(trigger: str, reason: str) -> dict:
    return {
        "action_type": "ttlock_open",
        "payload": {
            "reason": reason,
            "trigger": trigger,
            "emergency": True,
        },
        "requires_execute_call": True,
    }


def _build_abort_decision_pending_action(runtime_abort: dict, safety_mode: str) -> dict:
    trigger = str(runtime_abort.get("trigger") or "manual_abort").strip().lower()
    required_confirmations = max(1, int(runtime_abort.get("required_confirmations") or 2))
    confirmations = max(0, int(runtime_abort.get("confirmations") or 0))
    reason_required = bool(runtime_abort.get("reason_required", True))
    reason = str(runtime_abort.get("reason") or "").strip() or None
    return {
        "action_type": "abort_decision",
        "payload": {
            "trigger": trigger,
            "safety_mode": safety_mode,
            "required_confirmations": required_confirmations,
            "confirmations": confirmations,
            "remaining_confirmations": max(0, required_confirmations - confirmations),
            "reason_required": reason_required,
            "reason": reason,
        },
        "requires_execute_call": False,
    }


def _invalidate_contract_and_archive_session(
    *,
    request: Request,
    session: ChastitySession,
    policy: dict,
    reason: str,
    now: datetime,
) -> dict:
    updated_policy = dict(policy) if isinstance(policy, dict) else {}

    generated_contract = updated_policy.setdefault("generated_contract", {})
    if not isinstance(generated_contract, dict):
        generated_contract = {}
        updated_policy["generated_contract"] = generated_contract
    consent = generated_contract.setdefault("consent", {})
    if not isinstance(consent, dict):
        consent = {}
        generated_contract["consent"] = consent

    consent["accepted"] = False
    consent["accepted_at"] = None
    consent["consent_text"] = None
    consent["invalidated"] = True
    consent["invalidated_at"] = _iso_utc(now)
    consent["invalidated_reason"] = reason
    generated_contract["is_valid"] = False

    session.status = "archived"
    session.policy_snapshot_json = json.dumps(updated_policy)
    session.updated_at = now

    setup_session_id = find_setup_session_id_for_active_session(session.user_id, session.id)
    if setup_session_id:
        store = load_sessions()
        setup_session = store.get(setup_session_id)
        if isinstance(setup_session, dict):
            setup_session["status"] = "archived"
            setup_session["active_session_id"] = None
            setup_session["updated_at"] = _iso_utc(now)
            policy_preview = setup_session.get("policy_preview") if isinstance(setup_session.get("policy_preview"), dict) else {}
            setup_generated_contract = policy_preview.get("generated_contract") if isinstance(policy_preview.get("generated_contract"), dict) else {}
            setup_consent = setup_generated_contract.get("consent") if isinstance(setup_generated_contract.get("consent"), dict) else {}
            setup_consent["accepted"] = False
            setup_consent["accepted_at"] = None
            setup_consent["consent_text"] = None
            setup_consent["invalidated"] = True
            setup_consent["invalidated_at"] = _iso_utc(now)
            setup_consent["invalidated_reason"] = reason
            setup_generated_contract["consent"] = setup_consent
            setup_generated_contract["is_valid"] = False
            policy_preview["generated_contract"] = setup_generated_contract
            setup_session["policy_preview"] = policy_preview
            store[setup_session_id] = setup_session
            save_sessions(store)

    return updated_policy


def _extract_abort_trigger(message: str, psychogram: dict) -> str | None:
    safety = psychogram.get("safety_profile") if isinstance(psychogram.get("safety_profile"), dict) else {}
    mode = str(safety.get("mode") or "safeword").strip().lower()

    manual_abort_hints = {
        "rot",
        "red",
        "abbruch",
        "abbrechen",
        "notfall",
        "notfall stop",
        "session abbrechen",
        "sofort beenden",
        "sofort stoppen",
        "stop",
        "stopp",
        "emergency stop",
        "abort session",
    }
    if any(_contains_word(message, hint) for hint in manual_abort_hints):
        return "manual_abort"

    if mode == "safeword":
        safeword = str(safety.get("safeword") or "").strip()
        if safeword and _contains_word(message, safeword):
            return "safeword"
        return None

    if mode == "traffic_light":
        tl = safety.get("traffic_light_words") if isinstance(safety.get("traffic_light_words"), dict) else {}
        red_word = str(tl.get("red") or "red").strip()
        if red_word and _contains_word(message, red_word):
            return "traffic_red"
    return None


def _abort_protocol(safety: dict, trigger: str) -> tuple[int, bool]:
    if trigger == "safeword":
        protocol = safety.get("safeword_abort_protocol") if isinstance(safety.get("safeword_abort_protocol"), dict) else {}
    else:
        protocol = safety.get("red_abort_protocol") if isinstance(safety.get("red_abort_protocol"), dict) else {}
    confirmations = int(protocol.get("confirmation_questions_required") or 2)
    reason_required = bool(protocol.get("reason_required", True))
    return max(1, confirmations), reason_required


def _handle_emergency_abort_message(
    *,
    message: str,
    request_lang: str,
    policy: dict,
    psychogram: dict,
    now: datetime,
) -> tuple[bool, str | None, list[dict], dict, list[dict]]:
    runtime_abort = policy.get("runtime_abort") if isinstance(policy.get("runtime_abort"), dict) else None
    safety = psychogram.get("safety_profile") if isinstance(psychogram.get("safety_profile"), dict) else {}
    safety_mode = str(safety.get("mode") or "safeword").strip().lower()
    events: list[dict] = []

    if runtime_abort is None:
        trigger = _extract_abort_trigger(message, psychogram)
        if not trigger:
            return False, None, [], policy, events
        required, reason_required = _abort_protocol(safety, trigger)
        policy["runtime_abort"] = {
            "trigger": trigger,
            "required_confirmations": required,
            "confirmations": 0,
            "reason_required": reason_required,
            "reason": None,
            "created_at": _iso_utc(now),
        }
        text = (
            "Ich habe ein moegliches Notfallsignal erkannt. Bitte kurz einordnen: ABBRECHEN oder NICHT ABBRECHEN (mit Begruendung)."
            if request_lang == "de"
            else "Emergency abort detected. Please decide in the action card: ABORT or DO NOT ABORT (reason required)."
        )
        pending = [_build_abort_decision_pending_action(policy["runtime_abort"], safety_mode)]
        events.append(
            {
                "event_type": "abort_trigger_detected",
                "detail": "Abort trigger detected and confirmation flow initiated.",
                "metadata": {
                    "trigger": trigger,
                    "required_confirmations": required,
                    "reason_required": reason_required,
                    "safety_mode": safety_mode,
                },
            }
        )
        return True, text, pending, policy, events

    confirmations = int(runtime_abort.get("confirmations") or 0)
    required_confirmations = int(runtime_abort.get("required_confirmations") or 2)
    reason_required = bool(runtime_abort.get("reason_required", True))
    reason_text = str(runtime_abort.get("reason") or "").strip()
    trigger = str(runtime_abort.get("trigger") or "manual_abort").strip().lower()
    msg = str(message or "").strip()

    if _is_abort_cancellation_message(msg):
        policy.pop("runtime_abort", None)
        text = (
            "Danke fuer die Einordnung. Kein Abbruch - die Session bleibt aktiv."
            if request_lang == "de"
            else "Abort dismissed. Session remains active. Thanks for the clarification."
        )
        events.append(
            {
                "event_type": "abort_cancelled",
                "detail": "Emergency abort flow cancelled by wearer confirmation.",
                "metadata": {
                    "trigger": trigger,
                    "confirmations": confirmations,
                },
            }
        )
        return True, text, [], policy, events

    if not reason_text and reason_required and len(msg) >= 8 and not _is_confirmation_message(msg):
        reason_text = msg
        confirmations += 1
    elif _is_confirmation_message(msg):
        confirmations += 1

    if confirmations >= required_confirmations and (not reason_required or bool(reason_text)):
        reason = reason_text or "abort_confirmed"
        runtime_abort["confirmations"] = confirmations
        runtime_abort["reason"] = reason
        policy["runtime_abort"] = runtime_abort
        pending = [_build_emergency_ttlock_open_pending_action(trigger=trigger, reason=reason)]
        text = (
            "Danke fuer die Einordnung. Notfallablauf wird jetzt ausgefuehrt: Notfall-Oeffnung (ttlock_open), danach Invalidierung von Session und Vertrag."
            if request_lang == "de"
            else "Abort confirmed. Emergency opening (ttlock_open) is now triggered directly; session and contract will then be invalidated."
        )
        events.append(
            {
                "event_type": "abort_confirmed",
                "detail": "Emergency abort confirmed and ttlock_open pending action scheduled.",
                "metadata": {
                    "trigger": trigger,
                    "required_confirmations": required_confirmations,
                    "confirmations": confirmations,
                    "reason": reason,
                },
            }
        )
        return True, text, pending, policy, events

    runtime_abort["confirmations"] = confirmations
    runtime_abort["reason"] = reason_text or None
    policy["runtime_abort"] = runtime_abort
    remaining = max(0, required_confirmations - confirmations)
    if reason_required and not reason_text:
        text = (
            f"Bestaetigung erfasst. Es fehlen noch {remaining} Bestaetigung(en). Bitte gib zusaetzlich eine Begruendung an."
            if request_lang == "de"
            else f"Abort confirmation recorded. {remaining} confirmation(s) remaining. Please also provide a reason."
        )
    else:
        text = (
            f"Bestaetigung erfasst. Es fehlen noch {remaining} Bestaetigung(en)."
            if request_lang == "de"
            else f"Abort confirmation recorded. {remaining} confirmation(s) remaining."
        )
    pending = [_build_abort_decision_pending_action(runtime_abort, safety_mode)]
    return True, text, pending, policy, events


def _timer_expiry_pending_action(request_lang: str, policy: dict, now: datetime) -> tuple[str | None, list[dict], dict]:
    timer = _ensure_timer_state(policy, now)
    timer["remaining_seconds"] = _remaining_seconds(timer, now)
    policy["runtime_timer"] = timer
    if timer["remaining_seconds"] > 0:
        return None, [], policy
    if bool(policy.get("runtime_timer_expiry_handled")):
        return None, [], policy
    policy["runtime_timer_expiry_handled"] = True
    integrations = [str(item).strip().lower() for item in (policy.get("integrations") or []) if str(item).strip()]
    runtime_timer = policy.get("runtime_timer") if isinstance(policy.get("runtime_timer"), dict) else {}
    chaster_blocked = (
        "chaster" in integrations
        and runtime_timer.get("can_be_unlocked") is False
        and runtime_timer.get("is_ready_to_unlock") is False
    )
    blocking_reasons = [str(item).strip() for item in (runtime_timer.get("reasons_preventing_unlocking") or []) if str(item).strip()]
    if "chaster" in integrations:
        if chaster_blocked:
            reason_suffix = f" Gruende: {', '.join(blocking_reasons)}." if (request_lang == "de" and blocking_reasons) else ""
            reason_suffix_en = f" Reasons: {', '.join(blocking_reasons)}." if blocking_reasons else ""
            text = (
                f"Timer ist abgelaufen. Die Sitzung bleibt aktiv, weil Chaster das Entsperren derzeit nicht erlaubt.{reason_suffix}"
                if request_lang == "de"
                else f"Timer has expired. The session stays active because Chaster does not currently allow unlocking.{reason_suffix_en}"
            )
            return text, [], policy
        text = (
            "Timer ist abgelaufen. Es erfolgt keine automatische Oeffnung. Bitte Chaster pruefen und die Freigabe manuell ausloesen."
            if request_lang == "de"
            else "Timer has expired. No automatic opening will be triggered. Please check Chaster and perform the unlock manually."
        )
        return text, [], policy

    pending = [_build_hygiene_open_pending_action(policy, trigger="timer_expired", reason="timer_expired")]
    text = (
        "Timer ist abgelaufen. Bitte bestaetige die Hygieneoeffnung in der Actionkarte."
        if request_lang == "de"
        else "Timer has expired. Please confirm hygiene opening in the action card."
    )
    return text, pending, policy


def _fallback_pending_action_from_user_intent(message: str, policy: dict) -> dict | None:
    normalized = _normalize_text(message)
    runtime_timer = (policy or {}).get("runtime_timer") if isinstance((policy or {}).get("runtime_timer"), dict) else {}
    runtime_hygiene = (policy or {}).get("runtime_hygiene") if isinstance((policy or {}).get("runtime_hygiene"), dict) else {}
    hygiene_is_open = bool(runtime_hygiene.get("is_open"))
    timer_state = str(runtime_timer.get("state") or "running").strip().lower()
    pause_hints = {
        "pause",
        "pausieren",
        "pause timer",
        "timer pause",
        "freeze",
        "freeze timer",
        "timer freeze",
        "anhalten",
        "timer anhalten",
        "timer stoppen",
        "stop timer",
    }
    resume_hints = {
        "resume",
        "resume timer",
        "unfreeze",
        "weiter",
        "fortsetzen",
        "timer fortsetzen",
        "timer weiter",
        "unpause",
        "unpause timer",
    }
    open_hints = {
        "hygieneoffnung",
        "hygieneoeffnung",
        "hygiene oeffnung",
        "hygieneoffnen",
        "hygieneoeffnen",
        "hygiene oeffnen",
        "hygieneoffnung",
        "kafig offnen",
        "kafig oeffnen",
        "oeffnen",
        "open",
        "unlock",
    }
    close_hints = {
        "hygiene schliessen",
        "hygiene schliessen",
        "hygieneschliessen",
        "hygiene schliessen",
        "kafig schliessen",
    }
    add_time_hints = {
        "add time",
        "addiere",
        "fuge",
        "fuege",
        "hinzu",
        "verlangere",
        "verlaengere",
        "erhohe",
        "erhöhe",
        "extend",
        "increase",
    }
    reduce_time_hints = {
        "reduce time",
        "verkurze",
        "verkürze",
        "ziehe",
        "abziehen",
        "remove",
        "decrease",
        "reduce",
        "senke",
    }

    duration_match = re.search(
        r"(?P<amount>\d+)\s*(?P<unit>sekunden|sekunde|seconds|second|s|minuten|minute|minutes|minute|min|stunden|stunde|hours|hour|hrs|hr|h|tage|tag|days|day|d)\b",
        normalized,
    )
    duration_seconds = None
    if duration_match:
        amount = int(duration_match.group("amount"))
        unit = str(duration_match.group("unit") or "").strip().lower()
        unit_map = {
            "sekunde": "seconds",
            "sekunden": "seconds",
            "second": "seconds",
            "seconds": "seconds",
            "s": "seconds",
            "minute": "minutes",
            "minuten": "minutes",
            "minutes": "minutes",
            "min": "minutes",
            "stunde": "hours",
            "stunden": "hours",
            "hour": "hours",
            "hours": "hours",
            "hr": "hours",
            "hrs": "hours",
            "h": "hours",
            "tag": "days",
            "tage": "days",
            "day": "days",
            "days": "days",
            "d": "days",
        }
        duration_seconds = _normalize_duration_payload(
            "add_time",
            {"amount": amount, "unit": unit_map.get(unit, unit)},
        ).get("seconds")

    if duration_seconds and any(hint in normalized for hint in add_time_hints):
        return {
            "action_type": "add_time",
            "payload": {"seconds": int(duration_seconds)},
            "requires_execute_call": True,
        }

    if duration_seconds and any(hint in normalized for hint in reduce_time_hints):
        return {
            "action_type": "reduce_time",
            "payload": {"seconds": int(duration_seconds)},
            "requires_execute_call": True,
        }

    if any(hint in normalized for hint in pause_hints):
        if timer_state == "paused":
            return None
        return {
            "action_type": "pause_timer",
            "payload": {},
            "requires_execute_call": True,
        }

    if any(hint in normalized for hint in resume_hints):
        if timer_state != "paused":
            return None
        return {
            "action_type": "unpause_timer",
            "payload": {},
            "requires_execute_call": True,
        }

    if any(hint in normalized for hint in open_hints):
        if hygiene_is_open:
            return None
        return _build_hygiene_open_pending_action(
            policy,
            trigger="user_intent_fallback",
            reason="user_requested_hygiene_open",
        )

    if any(hint in normalized for hint in close_hints):
        if not hygiene_is_open:
            return None
        return {
            "action_type": "hygiene_close",
            "payload": {
                "trigger": "user_intent_fallback",
                "reason": "user_requested_hygiene_close",
            },
            "requires_execute_call": True,
        }

    return None


def _repair_missing_request_tag(
    *,
    db,
    request: Request,
    session: ChastitySession,
    request_lang: str,
    user_message: str,
    narration_raw: str,
) -> tuple[list[dict], bool]:
    repair_prompt = (
        (
            "FORMAT CORRECTION ONLY. Convert the assistant reply into exactly one machine line. "
            "Return either one valid line [[REQUEST:<action_type>|<json_payload>]] or NO_ACTION. "
            "No prose.\n\n"
            f"User message: {user_message}\n"
            f"Assistant reply: {narration_raw}"
        )
        if request_lang == "en"
        else (
            "NUR FORMAT-KORREKTUR. Wandle die Assistenten-Antwort in genau eine Machine-Zeile um. "
            "Antworte entweder mit genau einer gueltigen Zeile [[REQUEST:<action_type>|<json_payload>]] oder NO_ACTION. "
            "Kein Fliesstext.\n\n"
            f"User message: {user_message}\n"
            f"Assistant reply: {narration_raw}"
        )
    )
    repair_raw = generate_ai_narration_for_session(
        db,
        request,
        session,
        repair_prompt,
        request_lang,
        [],
    )
    _narration_unused, repaired_actions, _files_unused = extract_pending_actions(repair_raw)
    return repaired_actions, bool(repaired_actions)


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
        clamped_to_max = False
        if max_end_at is not None and next_end_at > max_end_at:
            next_end_at = max_end_at
            clamped_to_max = True
        effective_end_at = next_end_at
        timer["effective_end_at"] = _iso_utc(effective_end_at)
        timer["last_action"] = "add_time"
        timer["last_action_at"] = _iso_utc(now)
        policy.pop("runtime_timer_expiry_handled", None)
        policy.pop("runtime_timer_expiry_open_prompted", None)
        message = "Time added (clamped to max end date boundary)." if clamped_to_max else "Time added."
    elif action == "reduce_time":
        seconds = int(payload.get("seconds", 0))
        if seconds <= 0:
            raise HTTPException(status_code=400, detail="Action 'reduce_time' requires seconds > 0.")
        next_end_at = effective_end_at - timedelta(seconds=seconds)
        clamped_to_min = False
        if min_end_at is not None and next_end_at < min_end_at:
            next_end_at = min_end_at
            clamped_to_min = True
        effective_end_at = next_end_at
        timer["effective_end_at"] = _iso_utc(effective_end_at)
        timer["last_action"] = "reduce_time"
        timer["last_action_at"] = _iso_utc(now)
        message = "Time reduced (clamped to min end date boundary)." if clamped_to_min else "Time reduced."
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
        # Normalize duration payloads (e.g., amount+unit -> seconds) so pending actions
        # carry a consistent payload representation expected by the frontend/tests.
        try:
            normalized_payload = _normalize_duration_payload(normalized_action or raw_action_type, normalized_payload)
        except Exception:
            # Keep original payload if normalization fails
            normalized_payload = dict(normalized_payload or {})

        normalized.append(
            {
                "action_type": normalized_action or raw_action_type,
                "payload": normalized_payload,
                "requires_execute_call": bool((action or {}).get("requires_execute_call", True)),
            }
        )
    return normalized


def _dedupe_pending_actions(pending_actions: list[dict]) -> list[dict]:
    normalized = _normalize_pending_actions(pending_actions)
    deduplicated: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for action in normalized:
        action_type = str(action.get("action_type") or "").strip().lower()
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        fingerprint = (
            action_type,
            json.dumps(payload, sort_keys=True, ensure_ascii=True),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduplicated.append(action)
    return deduplicated


def _pending_action_key(action_type: str, payload: dict) -> tuple[str, str]:
    normalized_action = str(action_type or "").strip().lower()
    normalized_payload = payload if isinstance(payload, dict) else {}
    return (
        normalized_action,
        json.dumps(normalized_payload, sort_keys=True, ensure_ascii=True),
    )


def _with_action_ids_from_pending_rows(pending_actions: list[dict], pending_rows: list[dict]) -> list[dict]:
    """Attach action_id to pending action payloads using authoritative pending rows."""
    id_by_key: dict[tuple[str, str], str] = {}
    for row in pending_rows:
        action_type = str((row or {}).get("action_type") or "")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        action_id = str((row or {}).get("action_id") or "").strip()
        if not action_id:
            continue
        id_by_key[_pending_action_key(action_type, payload)] = action_id

    with_ids: list[dict] = []
    for action in pending_actions:
        action_type = str((action or {}).get("action_type") or "")
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        merged = dict(action or {})
        if not str(merged.get("action_id") or "").strip():
            resolved_id = id_by_key.get(_pending_action_key(action_type, payload), "")
            if resolved_id:
                merged["action_id"] = resolved_id
        with_ids.append(merged)
    return with_ids


def _pending_action_id(event_id: str, turn_id: str | None, action_type: str, payload: dict) -> str:
    raw = (
        f"{event_id}:{turn_id or '-'}:{str(action_type or '').strip().lower()}:"
        f"{json.dumps(payload if isinstance(payload, dict) else {}, sort_keys=True, ensure_ascii=True)}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load_entry_metadata(entry: AuditEntry) -> dict:
    metadata = {}
    if entry.metadata_json:
        try:
            metadata = json.loads(entry.metadata_json)
        except Exception:
            metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def _collect_pending_actions_for_session(db, session_id: str) -> list[dict]:
    entries = db.scalars(
        select(AuditEntry)
        .where(
            AuditEntry.session_id == session_id,
            AuditEntry.event_type.in_(["activity_snapshot", "activity_manual_execute", "activity_manual_resolve"]),
        )
        .order_by(AuditEntry.created_at.desc())
    ).all()
    turns = db.scalars(
        select(Turn)
        .where(Turn.session_id == session_id)
        .order_by(Turn.turn_no.desc())
    ).all()
    turn_map = {turn.id: turn for turn in turns}

    resolved_action_ids: set[str] = set()
    resolved_action_keys: set[tuple[str, str]] = set()
    pending_rows: list[dict] = []

    for entry in entries:
        metadata = _load_entry_metadata(entry)
        if entry.event_type in {"activity_manual_execute", "activity_manual_resolve"}:
            status = str(metadata.get("status") or "").strip().lower()
            if status in {"success", "failed", "canceled"}:
                action_id = str(metadata.get("action_id") or "").strip()
                if action_id:
                    resolved_action_ids.add(action_id)
                action_type = str(metadata.get("action_type") or "")
                payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
                resolved_action_keys.add(_pending_action_key(action_type, payload))
            continue

        turn = turn_map.get(entry.turn_id) if entry.turn_id else None
        pending_actions = metadata.get("pending_actions") if isinstance(metadata.get("pending_actions"), list) else []
        executed_actions = metadata.get("executed_actions") if isinstance(metadata.get("executed_actions"), list) else []
        failed_actions = metadata.get("failed_actions") if isinstance(metadata.get("failed_actions"), list) else []

        for action in executed_actions + failed_actions:
            action_type = str((action or {}).get("action_type") or "")
            payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
            resolved_action_keys.add(_pending_action_key(action_type, payload))

        for action in pending_actions:
            action_type = str((action or {}).get("action_type") or "")
            payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
            action_id = _pending_action_id(entry.id, entry.turn_id, action_type, payload)
            action_key = _pending_action_key(action_type, payload)
            if action_id in resolved_action_ids or action_key in resolved_action_keys:
                continue
            pending_rows.append(
                {
                    "action_id": action_id,
                    "event_id": entry.id,
                    "turn_id": entry.turn_id,
                    "turn_no": turn.turn_no if turn else None,
                    "action_type": action_type,
                    "payload": payload,
                    "detail": "Waiting for execute confirmation.",
                    "created_at": entry.created_at.isoformat(),
                    "expected_status": "pending",
                }
            )

    return pending_rows


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


def _chaster_from_policy(policy: dict) -> dict:
    integration_config = policy.get("integration_config")
    if not isinstance(integration_config, dict):
        return {}
    chaster = integration_config.get("chaster")
    return chaster if isinstance(chaster, dict) else {}


def _get_chaster_developer_headers(request: Request) -> dict[str, str]:
    token = str(getattr(request.app.state.config, "CHASTER_DEVELOPER_TOKEN", "") or "").strip()
    if not token:
        raise HTTPException(status_code=500, detail="CHASTER_DEVELOPER_TOKEN is not configured.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get_chaster_developer_base(request: Request) -> str:
    base = str(getattr(request.app.state.config, "CHASTER_DEVELOPER_API_BASE", "https://api.chaster.app/api") or "").strip()
    base = base.rstrip("/")
    if not base:
        raise HTTPException(status_code=500, detail="CHASTER_DEVELOPER_API_BASE is empty.")
    return base


def _resolve_chaster_extension_session(*, policy: dict, request: Request) -> tuple[str, dict]:
    chaster_cfg = _chaster_from_policy(policy)
    lock_id = str(chaster_cfg.get("lock_id") or "").strip()
    if not lock_id:
        raise HTTPException(status_code=409, detail="Chaster lock_id is missing.")

    main_token_enc = str(chaster_cfg.get("extension_main_token_enc") or "").strip()
    if main_token_enc:
        try:
            main_token = decrypt_secret(main_token_enc, request.app.state.config.SECRET_KEY)
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Stored Chaster extension mainToken is invalid.") from exc
        session_id, verified_payload = resolve_verified_extension_session_from_main_token_sync(main_token, request)
        integration_config = policy.get("integration_config") if isinstance(policy.get("integration_config"), dict) else {}
        merged_chaster = dict(chaster_cfg)
        merged_chaster["extension_session_id"] = session_id
        merged_chaster["extension_session_snapshot"] = {
            "id": session_id,
            "lock_id": lock_id,
            "slug": str(((verified_payload.get("session") or {}).get("extension") or {}).get("slug") or verified_payload.get("extensionSlug") or chaster_cfg.get("extension_slug") or "").strip() or None,
        }
        integration_config["chaster"] = merged_chaster
        policy["integration_config"] = integration_config
        return session_id, merged_chaster

    cached_session_id = str(chaster_cfg.get("extension_session_id") or "").strip()
    if cached_session_id:
        return cached_session_id, chaster_cfg

    # Fallback: search live via developer token — no wearer action needed
    extension_slug = str(getattr(request.app.state.config, "CHASTER_EXTENSION_SLUG", "") or "").strip()
    dev_base = _get_chaster_developer_base(request)
    dev_headers = _get_chaster_developer_headers(request)
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            search_resp = client.post(
                f"{dev_base}/extensions/sessions/search",
                headers=dev_headers,
                json={"extensionSlug": extension_slug, "limit": 100},
            )
        if search_resp.status_code < 400:
            try:
                search_json = search_resp.json()
            except (ValueError, KeyError):
                search_json = {}
            from chastease.api.routers.chaster import _find_extension_session_id as _chaster_find_session
            live_session_id = _chaster_find_session(search_json, lock_id)
            if live_session_id:
                integration_config = policy.get("integration_config") if isinstance(policy.get("integration_config"), dict) else {}
                merged_chaster = dict(chaster_cfg)
                merged_chaster["extension_session_id"] = live_session_id
                integration_config["chaster"] = merged_chaster
                policy["integration_config"] = integration_config
                logger.info("Chaster extension_session_id resolved via live search for lock_id=%s", lock_id)
                return live_session_id, merged_chaster
    except Exception as exc:
        logger.warning("Chaster live extension session search failed: %s", exc)

    raise HTTPException(
        status_code=409,
        detail=(
            f"Chaster extension_session_id could not be resolved for lock_id={lock_id}. "
            "Ensure the Chaster extension is configured and CHASTER_DEVELOPER_TOKEN / CHASTER_EXTENSION_SLUG are set."
        ),
    )


def _sync_chaster_lock_time_change(
    *,
    action_type: str,
    seconds: int,
    policy: dict,
    request: Request,
) -> dict | None:
    action = str(action_type or "").strip().lower()
    if action not in {"add_time", "reduce_time"}:
        return None
    if seconds <= 0:
        raise HTTPException(status_code=400, detail=f"Action '{action}' requires seconds > 0.")

    integrations = [str(x).strip().lower() for x in (policy.get("integrations") or []) if str(x).strip()]
    chaster_cfg = _chaster_from_policy(policy)
    if "chaster" not in integrations and not chaster_cfg:
        return None

    lock_id = str(chaster_cfg.get("lock_id") or "").strip()
    if not lock_id:
        raise HTTPException(
            status_code=409,
            detail="Chaster integration is enabled, but no lock_id is configured for this session.",
        )
    extension_session_id, merged_cfg = _resolve_chaster_extension_session(policy=policy, request=request)
    chaster_cfg = merged_cfg
    delta_seconds = seconds if action == "add_time" else -seconds
    action_name = "add_time" if action == "add_time" else "remove_time"
    base_url = _get_chaster_developer_base(request)
    headers = _get_chaster_developer_headers(request)
    payload = {
        "action": {
            "name": action_name,
            "params": abs(int(delta_seconds)),
        }
    }
    url = f"{base_url}/extensions/sessions/{extension_session_id}/action"
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Chaster extension action failed with HTTP {response.status_code}: {response.text[:500]}",
        )
    try:
        response_json = response.json()
    except (ValueError, KeyError):
        response_json = {"raw_response": response.text[:500]}
    return {
        "endpoint": url,
        "lock_id": lock_id,
        "extension_session_id": extension_session_id,
        "delta_seconds": delta_seconds,
        "identity_mode": "extension_developer_token",
        "identity_source": "developer_token",
        "payload": payload,
        "response": response_json,
    }


def _sync_chaster_freeze_state(
    *,
    freeze_enabled: bool,
    policy: dict,
    request: Request,
) -> dict | None:
    integrations = [str(x).strip().lower() for x in (policy.get("integrations") or []) if str(x).strip()]
    chaster_cfg = _chaster_from_policy(policy)
    if "chaster" not in integrations and not chaster_cfg:
        return None

    lock_id = str(chaster_cfg.get("lock_id") or "").strip()
    if not lock_id:
        raise HTTPException(
            status_code=409,
            detail="Chaster integration is enabled, but no lock_id is configured for this session.",
        )
    extension_session_id, merged_cfg = _resolve_chaster_extension_session(policy=policy, request=request)
    chaster_cfg = merged_cfg
    base_url = _get_chaster_developer_base(request)
    headers = _get_chaster_developer_headers(request)
    action_name = "freeze" if freeze_enabled else "unfreeze"
    url = f"{base_url}/extensions/sessions/{extension_session_id}/action"
    payload = {
        "action": {
            "name": action_name,
        }
    }
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Chaster extension freeze action failed with HTTP {response.status_code}: {response.text[:500]}",
        )
    try:
        response_json = response.json()
    except (ValueError, KeyError):
        response_json = {"raw_response": response.text[:500] or ""}
    return {
        "endpoint": url,
        "lock_id": lock_id,
        "extension_session_id": extension_session_id,
        "freeze_enabled": freeze_enabled,
        "identity_mode": "extension_developer_token",
        "identity_source": "developer_token",
        "payload": payload,
        "response": response_json,
    }


def _sync_chaster_temporary_opening(*, policy: dict, request: Request) -> dict | None:
    integrations = [str(x).strip().lower() for x in (policy.get("integrations") or []) if str(x).strip()]
    chaster_cfg = _chaster_from_policy(policy)
    if "chaster" not in integrations and not chaster_cfg:
        return None

    lock_id = str(chaster_cfg.get("lock_id") or "").strip()
    if not lock_id:
        raise HTTPException(
            status_code=409,
            detail="Chaster integration is enabled, but no lock_id is configured for this session.",
        )

    extension_session_id, merged_cfg = _resolve_chaster_extension_session(policy=policy, request=request)
    chaster_cfg = merged_cfg
    base_url = _get_chaster_developer_base(request)
    headers = _get_chaster_developer_headers(request)
    payload = {"actor": "extension"}
    url = f"{base_url}/extensions/sessions/{extension_session_id}/temporary-opening/open"
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Chaster temporary-opening failed with HTTP {response.status_code}: {response.text[:500]}",
        )
    try:
        response_json = response.json()
    except (ValueError, KeyError):
        response_json = {"raw_response": response.text[:500] or ""}
    return {
        "endpoint": url,
        "lock_id": lock_id,
        "extension_session_id": extension_session_id,
        "identity_mode": "extension_developer_token",
        "identity_source": "developer_token",
        "payload": payload,
        "response": response_json,
    }


def _generate_nine_digit_code() -> str:
    return str(random.randint(100_000_000, 999_999_999))


def _sync_chaster_close_temporary_opening(*, policy: dict, request: Request, new_code: str) -> dict | None:
    integrations = [str(x).strip().lower() for x in (policy.get("integrations") or []) if str(x).strip()]
    chaster_cfg = _chaster_from_policy(policy)
    if "chaster" not in integrations and not chaster_cfg:
        return None

    lock_id = str(chaster_cfg.get("lock_id") or "").strip()
    if not lock_id:
        raise HTTPException(
            status_code=409,
            detail="Chaster integration is enabled, but no lock_id is configured for this session.",
        )

    # Step 1: Create combination via user token → get MongoDB combination_id
    lock_token, _resolved = resolve_chaster_api_token(chaster_cfg, request)
    if not lock_token:
        raise HTTPException(
            status_code=409,
            detail="Chaster user API token is missing — cannot create combination for hygiene close.",
        )
    base_url = _get_chaster_developer_base(request)
    timeout = httpx.Timeout(connect=6.0, read=25.0, write=20.0, pool=6.0)
    user_headers = {
        "Authorization": f"Bearer {lock_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    combinations_url = f"{base_url}/combinations/code"
    with httpx.Client(timeout=timeout) as client:
        combo_response = client.post(combinations_url, headers=user_headers, json={"code": new_code})
    if combo_response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Chaster combinations/code failed with HTTP {combo_response.status_code}: {combo_response.text[:500]}",
        )
    try:
        combo_json = combo_response.json()
    except (ValueError, KeyError):
        raise HTTPException(status_code=502, detail="Chaster combinations/code returned non-JSON response.")
    combination_id = None
    if isinstance(combo_json, dict):
        for key in ("_id", "id", "combinationId", "combination_id", "codeId"):
            val = combo_json.get(key)
            if val and str(val).strip():
                combination_id = str(val).strip()
                break
    if not combination_id:
        raise HTTPException(status_code=502, detail="Unable to resolve combination_id from Chaster combinations/code response.")

    # Step 2: Close temporary opening with developer token and combination_id
    extension_session_id, _merged_cfg = _resolve_chaster_extension_session(policy=policy, request=request)
    dev_headers = _get_chaster_developer_headers(request)
    close_payload = {"combinationId": combination_id}
    close_url = f"{base_url}/extensions/sessions/{extension_session_id}/temporary-opening/close"
    with httpx.Client(timeout=timeout) as client:
        close_response = client.post(close_url, headers=dev_headers, json=close_payload)
    if close_response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Chaster temporary-opening close failed with HTTP {close_response.status_code}: {close_response.text[:500]}",
        )
    try:
        close_response_json = close_response.json()
    except (ValueError, KeyError):
        close_response_json = {"raw_response": close_response.text[:500] or ""}
    return {
        "combinations_endpoint": combinations_url,
        "close_endpoint": close_url,
        "lock_id": lock_id,
        "extension_session_id": extension_session_id,
        "combination_id": combination_id,
        "new_code": new_code,
        "close_payload": close_payload,
        "close_response": close_response_json,
    }


def _ttlock_list_keyboard_passwords(
    *,
    base_url: str,
    client_id: str,
    access_token: str,
    lock_id: str,
) -> list[dict]:
    url = f"{base_url.rstrip('/')}/v3/lock/listKeyboardPassword"
    timeout = httpx.Timeout(connect=5.0, read=20.0, write=15.0, pool=5.0)
    params = {
        "clientId": client_id,
        "accessToken": access_token,
        "lockId": lock_id,
        "pageNo": 1,
        "pageSize": 100,
        "date": int(time.time() * 1000),
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"TT-Lock list keyboard passwords HTTP {resp.status_code}: {resp.text[:220].strip()}",
            )
        body = resp.json()
        if body.get("errcode", 0) not in (0, "0"):
            raise HTTPException(
                status_code=400,
                detail=f"TT-Lock list keyboard passwords failed: {body.get('errmsg', 'unknown error')}",
            )
        return body.get("list", []) or []
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="TT-Lock list keyboard passwords timeout.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"TT-Lock list keyboard passwords transport error: {exc.__class__.__name__}")


def _ttlock_delete_keyboard_password(
    *,
    base_url: str,
    client_id: str,
    access_token: str,
    lock_id: str,
    keyboard_pwd_id: int,
) -> dict:
    url = f"{base_url.rstrip('/')}/v3/keyboardPwd/delete"
    timeout = httpx.Timeout(connect=5.0, read=20.0, write=15.0, pool=5.0)
    params = {
        "clientId": client_id,
        "accessToken": access_token,
        "lockId": lock_id,
        "keyboardPwdId": keyboard_pwd_id,
        "deleteType": 2,
        "date": int(time.time() * 1000),
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"TT-Lock delete keyboard password HTTP {resp.status_code}: {resp.text[:220].strip()}",
            )
        body = resp.json()
        if body.get("errcode", 0) not in (0, "0"):
            raise HTTPException(
                status_code=400,
                detail=f"TT-Lock delete keyboard password failed: {body.get('errmsg', 'unknown error')}",
            )
        return body
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="TT-Lock delete keyboard password timeout.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"TT-Lock delete keyboard password transport error: {exc.__class__.__name__}")


def _ttlock_add_keyboard_password(
    *,
    base_url: str,
    client_id: str,
    access_token: str,
    lock_id: str,
    code: str,
) -> dict:
    url = f"{base_url.rstrip('/')}/v3/keyboardPwd/add"
    timeout = httpx.Timeout(connect=5.0, read=20.0, write=15.0, pool=5.0)
    params = {
        "clientId": client_id,
        "accessToken": access_token,
        "lockId": lock_id,
        "alias": "Hygiene-Code",
        "keyboardPwd": code,
        "startDate": 0,
        "endDate": 0,
        "addType": 1,
        "date": int(time.time() * 1000),
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"TT-Lock add keyboard password HTTP {resp.status_code}: {resp.text[:220].strip()}",
            )
        body = resp.json()
        if body.get("errcode", 0) not in (0, "0"):
            raise HTTPException(
                status_code=400,
                detail=f"TT-Lock add keyboard password failed: {body.get('errmsg', 'unknown error')}",
            )
        return body
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="TT-Lock add keyboard password timeout.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"TT-Lock add keyboard password transport error: {exc.__class__.__name__}")


def _ttlock_replace_sole_passcode(
    *,
    base_url: str,
    client_id: str,
    access_token: str,
    lock_id: str,
    code: str,
) -> dict:
    existing = _ttlock_list_keyboard_passwords(
        base_url=base_url,
        client_id=client_id,
        access_token=access_token,
        lock_id=lock_id,
    )
    deleted_ids: list[int] = []
    for pwd in existing:
        pwd_id = pwd.get("keyboardPwdId")
        if pwd_id is not None:
            _ttlock_delete_keyboard_password(
                base_url=base_url,
                client_id=client_id,
                access_token=access_token,
                lock_id=lock_id,
                keyboard_pwd_id=int(pwd_id),
            )
            deleted_ids.append(int(pwd_id))
    add_result = _ttlock_add_keyboard_password(
        base_url=base_url,
        client_id=client_id,
        access_token=access_token,
        lock_id=lock_id,
        code=code,
    )
    return {
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "add_result": add_result,
    }


def _opening_window_start(now: datetime, period: str) -> datetime:
    normalized = str(period or "day").strip().lower()
    if normalized == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if normalized == "week":
        weekday = now.weekday()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_day - timedelta(days=weekday)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_emergency_open(payload: dict) -> bool:
    if bool(payload.get("emergency", False)):
        return True
    trigger = str(payload.get("trigger") or "").strip().lower()
    return trigger in {"manual_abort", "safeword", "traffic_red"}


def _seal_mode_from_policy(policy: dict) -> str:
    seal_cfg = policy.get("seal") if isinstance(policy.get("seal"), dict) else {}
    mode = str(seal_cfg.get("mode") or "none").strip().lower()
    if mode not in {"none", "plomben", "versiegelung"}:
        return "none"
    return mode


def _assert_opening_limit_allows_open(policy: dict, payload: dict, now: datetime) -> None:
    if _is_emergency_open(payload):
        return

    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    opening_period = str(limits.get("opening_limit_period") or "day").strip().lower()
    if opening_period not in {"day", "week", "month"}:
        opening_period = "day"

    raw_limit = limits.get("max_openings_in_period", limits.get("max_openings_per_day", 1))
    try:
        max_openings = int(raw_limit)
    except (TypeError, ValueError):
        max_openings = 1
    max_openings = max(0, max_openings)

    runtime_limits = policy.get("runtime_opening_limits") if isinstance(policy.get("runtime_opening_limits"), dict) else {}
    raw_events = runtime_limits.get("open_events") if isinstance(runtime_limits.get("open_events"), list) else []

    parsed_events: list[datetime] = []
    for item in raw_events:
        if not isinstance(item, str):
            continue
        parsed = _parse_iso_dt(item)
        if parsed is not None:
            parsed_events.append(parsed)

    window_start = _opening_window_start(now, opening_period)
    events_in_window = [dt for dt in parsed_events if dt >= window_start]

    if max_openings <= 0:
        raise HTTPException(
            status_code=409,
            detail=f"Opening limit reached for period '{opening_period}' (0 openings allowed).",
        )
    if len(events_in_window) >= max_openings:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Opening limit reached for period '{opening_period}' "
                f"({len(events_in_window)}/{max_openings} used)."
            ),
        )


def _record_open_event(policy: dict, now: datetime) -> None:
    runtime_limits = policy.get("runtime_opening_limits") if isinstance(policy.get("runtime_opening_limits"), dict) else {}
    raw_events = runtime_limits.get("open_events") if isinstance(runtime_limits.get("open_events"), list) else []

    parsed_events: list[datetime] = []
    for item in raw_events:
        if not isinstance(item, str):
            continue
        parsed = _parse_iso_dt(item)
        if parsed is not None:
            parsed_events.append(parsed)

    retention_start = now - timedelta(days=90)
    retained = [dt for dt in parsed_events if dt >= retention_start]
    retained.append(now)
    retained.sort()

    runtime_limits["open_events"] = [_iso_utc(dt) for dt in retained]
    policy["runtime_opening_limits"] = runtime_limits


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
    ttlock_enabled = "ttlock" in integrations or bool(config)
    hygiene_without_ttlock = action_type in _HYGIENE_ACTIONS and not ttlock_enabled
    if not ttlock_enabled and not hygiene_without_ttlock:
        raise HTTPException(status_code=400, detail="TT-Lock integration is not enabled in this session policy.")

    ttl_user = str(config.get("ttl_user") or "").strip()
    ttl_pass_md5 = str(config.get("ttl_pass_md5") or "").strip().lower()
    lock_id = str(payload.get("ttl_lock_id") or payload.get("lock_id") or config.get("ttl_lock_id") or "").strip()
    gateway_id = str(config.get("ttl_gateway_id") or "").strip() or None
    client_id = str(getattr(request.app.state.config, "TTL_CLIENT_ID", "") or "").strip()
    client_secret = str(getattr(request.app.state.config, "TTL_CLIENT_SECRET", "") or "").strip()
    base_url = str(getattr(request.app.state.config, "TTL_API_BASE", "https://euapi.ttlock.com") or "").strip()

    command = "open" if str(action_type).endswith("_open") else "close"
    now = datetime.now(UTC)
    seal_mode = _seal_mode_from_policy(policy)
    seal_required_on_close = seal_mode in {"plomben", "versiegelung"}
    runtime_seal = policy.get("runtime_seal") if isinstance(policy.get("runtime_seal"), dict) else {}
    runtime_hygiene = policy.get("runtime_hygiene") if isinstance(policy.get("runtime_hygiene"), dict) else {}
    seal_text = str(payload.get("seal_text") or "").strip()
    if action_type == "hygiene_close" and seal_required_on_close and len(seal_text) < 3:
        raise HTTPException(
            status_code=400,
            detail="Seal text is required for hygiene_close when seal mode is enabled.",
        )
    if action_type == "hygiene_close" and not bool(runtime_hygiene.get("is_open")):
        raise HTTPException(
            status_code=409,
            detail="No active hygiene opening to close.",
        )
    if command == "open":
        _assert_opening_limit_allows_open(policy, payload, now)
    result_payload = None
    if ttlock_enabled:
        if not ttl_user or not ttl_pass_md5 or not lock_id:
            raise HTTPException(
                status_code=400,
                detail="TT-Lock configuration incomplete. Required: ttl_user, ttl_pass_md5, ttl_lock_id.",
            )
        if not client_id or not client_secret:
            raise HTTPException(status_code=400, detail="TT-Lock server config missing: TTL_CLIENT_ID / TTL_CLIENT_SECRET.")
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
    if command == "open":
        _record_open_event(policy, now)
        runtime_hygiene["is_open"] = True
        runtime_hygiene["opened_at"] = _iso_utc(now)
        runtime_hygiene["closed_at"] = None
        if action_type == "hygiene_open" and seal_required_on_close:
            runtime_seal["status"] = "broken"
            runtime_seal["broken_at"] = _iso_utc(now)
            runtime_seal["current_text"] = None
            runtime_seal["needs_new_seal"] = True
    elif action_type == "hygiene_close":
        runtime_hygiene["is_open"] = False
        runtime_hygiene["closed_at"] = _iso_utc(now)
        if seal_required_on_close:
            runtime_seal["status"] = "sealed"
            runtime_seal["sealed_at"] = _iso_utc(now)
            runtime_seal["current_text"] = seal_text
            runtime_seal["needs_new_seal"] = False

    policy["runtime_hygiene"] = runtime_hygiene
    if seal_required_on_close:
        policy["runtime_seal"] = runtime_seal
    if ttlock_enabled:
        logger.info(
            "TT-Lock command executed: action=%s lock_id=%s gateway_id=%s",
            action_type,
            lock_id,
            gateway_id or "-",
        )
    else:
        logger.info("Hygiene action executed without TT-Lock integration: action=%s", action_type)
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    opening_window_minutes = int(limits.get("opening_window_minutes") or 15)
    opening_window_minutes = max(1, min(opening_window_minutes, 240))
    opening_window_seconds = opening_window_minutes * 60
    window_end_at = (
        _iso_utc(datetime.now(UTC) + timedelta(seconds=opening_window_seconds))
        if command == "open"
        else None
    )
    if command == "open":
        runtime_hygiene["window_end_at"] = window_end_at
    else:
        runtime_hygiene["window_end_at"] = None
    policy["runtime_hygiene"] = runtime_hygiene
    return policy, {
        "action_type": action_type,
        "payload": {
            "lock_id": lock_id,
            "opening_window_minutes": opening_window_minutes,
            "opening_window_seconds": opening_window_seconds,
            "window_end_at": window_end_at,
            "seal_mode": seal_mode,
            "seal_required_on_close": seal_required_on_close,
            "seal_status": runtime_seal.get("status") if seal_required_on_close else "none",
            "seal_text": runtime_seal.get("current_text") if (seal_required_on_close and action_type == "hygiene_close") else None,
        },
        "ttlock": {
            "command": command,
            "lock_id": lock_id or None,
            "gateway_id": gateway_id,
            "response": result_payload,
            "executed": ttlock_enabled,
        },
        "message": (
            (
                f"TT-Lock opened. Hygiene window: {opening_window_minutes} minute(s)."
                if ttlock_enabled
                else f"Hygieneöffnung gestartet. Hygiene window: {opening_window_minutes} minute(s)."
            )
            if command == "open"
            else ("TT-Lock closed." if ttlock_enabled else "Hygieneöffnung beendet.")
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
        working_policy = copy.deepcopy(policy)
        updated_policy, timer_state, action_message = _apply_timer_action(
            normalized_action,
            normalized_payload,
            working_policy,
            now,
        )
        chaster_sync = None
        if normalized_action in {"add_time", "reduce_time"}:
            chaster_sync = _sync_chaster_lock_time_change(
                action_type=normalized_action,
                seconds=int(normalized_payload.get("seconds") or 0),
                policy=updated_policy,
                request=request,
            )
        elif normalized_action in {"pause_timer", "unpause_timer"}:
            chaster_sync = _sync_chaster_freeze_state(
                freeze_enabled=(normalized_action == "pause_timer"),
                policy=updated_policy,
                request=request,
            )
        return updated_policy, {
            "action_type": normalized_action,
            "payload": normalized_payload,
            "timer": timer_state,
            "chaster": chaster_sync,
            "message": action_message,
        }
    if normalized_action in _TTLOCK_ACTIONS:
        trigger = str(normalized_payload.get("trigger") or "").strip().lower()
        emergency_triggers = {"safeword", "traffic_red", "manual_abort"}
        if normalized_action == "ttlock_open" and trigger in emergency_triggers:
            return _execute_ttlock_action(
                action_type=normalized_action,
                payload=normalized_payload,
                policy=policy,
                request=request,
            )
        raise HTTPException(
            status_code=403,
            detail=(
                f"Action '{normalized_action}' is reserved for system-managed session lifecycle. "
                "Use 'hygiene_open' or 'hygiene_close' for interactive hygiene flows."
            ),
        )
    if normalized_action in _HYGIENE_ACTIONS:
        updated_policy, result = _execute_ttlock_action(
            action_type=normalized_action,
            payload=normalized_payload,
            policy=policy,
            request=request,
        )
        if normalized_action == "hygiene_open":
            result["chaster"] = _sync_chaster_temporary_opening(
                policy=updated_policy,
                request=request,
            )
        elif normalized_action == "hygiene_close":
            new_code = _generate_nine_digit_code()
            result["new_passcode"] = new_code
            if result.get("ttlock", {}).get("executed"):
                config = _ttlock_from_policy(updated_policy)
                lock_id = str(
                    normalized_payload.get("ttl_lock_id")
                    or normalized_payload.get("lock_id")
                    or config.get("ttl_lock_id")
                    or ""
                ).strip()
                client_id = str(getattr(request.app.state.config, "TTL_CLIENT_ID", "") or "").strip()
                client_secret = str(getattr(request.app.state.config, "TTL_CLIENT_SECRET", "") or "").strip()
                base_url = str(getattr(request.app.state.config, "TTL_API_BASE", "https://euapi.ttlock.com") or "").strip()
                ttl_user = str(config.get("ttl_user") or "").strip()
                ttl_pass_md5 = str(config.get("ttl_pass_md5") or "").strip().lower()
                access_token = _ttlock_access_token(
                    base_url=base_url,
                    client_id=client_id,
                    client_secret=client_secret,
                    ttl_user=ttl_user,
                    ttl_pass_md5=ttl_pass_md5,
                )
                result["ttlock"]["passcode_update"] = _ttlock_replace_sole_passcode(
                    base_url=base_url,
                    client_id=client_id,
                    access_token=access_token,
                    lock_id=lock_id,
                    code=new_code,
                )
                logger.info(
                    "TT-Lock passcode rotated after hygiene_close lock_id=%s deleted=%d",
                    lock_id,
                    result["ttlock"]["passcode_update"]["deleted_count"],
                )
            result["chaster"] = _sync_chaster_close_temporary_opening(
                policy=updated_policy,
                request=request,
                new_code=new_code,
            )
        return updated_policy, result
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
        if normalized_action in _TTLOCK_ACTIONS:
            trigger = str(payload_dict.get("trigger") or "").strip().lower()
            emergency_triggers = {"safeword", "traffic_red", "manual_abort"}
            should_force_execute_ttlock = normalized_action == "ttlock_open" and trigger in emergency_triggers
            if should_force_execute_ttlock:
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
                continue
        if normalized_action in _HYGIENE_ACTIONS:
            trigger = str(payload_dict.get("trigger") or "").strip().lower()
            emergency_triggers = {"safeword", "traffic_red", "manual_abort"}
            should_force_execute = trigger in emergency_triggers
            if should_force_execute:
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
                continue
            remaining_actions.append({
                "action_type": normalized_action,
                "payload": payload_dict,
                "requires_execute_call": True,
            })
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


def _clear_resolved_image_verification_pending(
    pending_actions: list[dict],
    verification_payload: dict,
) -> list[dict]:
    request_value = str((verification_payload or {}).get("request") or "").strip()
    instruction_value = str((verification_payload or {}).get("verification_instruction") or "").strip()
    remaining: list[dict] = []
    for action in pending_actions:
        action_type = _normalize_action_type(str((action or {}).get("action_type") or ""))
        payload = (action or {}).get("payload")
        payload_dict = dict(payload) if isinstance(payload, dict) else {}
        if action_type != "image_verification":
            remaining.append(action)
            continue
        action_request = str(payload_dict.get("request") or "").strip()
        action_instruction = str(payload_dict.get("verification_instruction") or "").strip()
        if action_request == request_value and action_instruction == instruction_value:
            continue
        remaining.append(action)
    return remaining


def _keep_single_latest_image_verification_pending(pending_actions: list[dict]) -> list[dict]:
    """Keep only one unresolved image_verification action (the most recent one)."""
    latest_index = -1
    for idx, action in enumerate(pending_actions):
        action_type = _normalize_action_type(str((action or {}).get("action_type") or ""))
        if action_type == "image_verification":
            latest_index = idx
    if latest_index < 0:
        return pending_actions

    filtered: list[dict] = []
    for idx, action in enumerate(pending_actions):
        action_type = _normalize_action_type(str((action or {}).get("action_type") or ""))
        if action_type != "image_verification" or idx == latest_index:
            filtered.append(action)
    return filtered


def _load_latest_pending_actions(db, session_id: str) -> list[dict]:
    """Load pending_actions from the most recent activity_snapshot audit entry."""
    latest_snapshot = (
        db.query(AuditEntry)
        .filter(
            AuditEntry.session_id == session_id,
            AuditEntry.event_type == "activity_snapshot",
        )
        .order_by(AuditEntry.created_at.desc())
        .first()
    )
    if latest_snapshot is None:
        return []
    metadata = json.loads(latest_snapshot.metadata_json or "{}") if latest_snapshot.metadata_json else {}
    if not isinstance(metadata, dict):
        return []
    pending = metadata.get("pending_actions")
    if not isinstance(pending, list):
        return []
    return pending


@router.post("/turn")
def chat_turn(payload: ChatTurnRequest, request: Request) -> dict:
    request_lang = lang(payload.language)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")

    action_text = message
    strict_request_tag_mode = bool(getattr(request.app.state.config, "LLM_FAIL_CLOSED_REQUEST_TAG", True))

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        audit_events_to_log: list[dict] = []

        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        psychogram = json.loads(session.psychogram_snapshot_json) if session.psychogram_snapshot_json else {}
        if not isinstance(psychogram, dict):
            psychogram = {}

        now = datetime.now(UTC)
        policy_dirty = False
        pending_actions: list[dict] = []
        executed_actions: list[dict] = []
        failed_actions: list[dict] = []
        generated_files: list[dict] = []
        raw_has_machine_tag = False
        fallback_applied = False
        reask_attempted = False
        reask_applied = False
        explicit_intent_action = _fallback_pending_action_from_user_intent(action_text, policy)

        # Load existing pending_actions from the latest activity_snapshot
        existing_pending_actions = _load_latest_pending_actions(db, payload.session_id)

        timer_narration, timer_pending, policy = _timer_expiry_pending_action(request_lang, policy, now)
        if timer_pending:
            policy_dirty = True
            pending_actions.extend(timer_pending)

        abort_handled, abort_narration, abort_pending, policy, abort_audit_events = _handle_emergency_abort_message(
            message=action_text,
            request_lang=request_lang,
            policy=policy,
            psychogram=psychogram,
            now=now,
        )
        audit_events_to_log.extend(abort_audit_events)
        if abort_handled:
            policy_dirty = True
            if abort_pending:
                interactive_abort_actions = [
                    action
                    for action in abort_pending
                    if str((action or {}).get("action_type") or "").strip().lower() == "abort_decision"
                ]
                auto_abort_actions = [
                    action
                    for action in abort_pending
                    if str((action or {}).get("action_type") or "").strip().lower() != "abort_decision"
                ]
                remaining_abort_actions: list[dict] = []
                executed_abort_actions: list[dict] = []
                failed_abort_actions: list[dict] = []
                updated_policy = policy
                if auto_abort_actions:
                    (
                        remaining_abort_actions,
                        executed_abort_actions,
                        failed_abort_actions,
                        updated_policy,
                    ) = _auto_execute_pending_actions(
                        request=request,
                        policy=policy,
                        pending_actions=auto_abort_actions,
                    )
                policy = updated_policy
                pending_actions.extend(interactive_abort_actions)
                pending_actions.extend(remaining_abort_actions)
                executed_actions.extend(executed_abort_actions)
                failed_actions.extend(failed_abort_actions)
                emergency_open_executed = any(
                    str(item.get("action_type") or "").strip().lower() == "ttlock_open"
                    for item in executed_abort_actions
                )
                if emergency_open_executed:
                    policy.pop("runtime_abort", None)
                    runtime_abort_reason = "emergency_abort_confirmed"
                    policy = _invalidate_contract_and_archive_session(
                        request=request,
                        session=session,
                        policy=policy,
                        reason=runtime_abort_reason,
                        now=now,
                    )
                elif failed_abort_actions:
                    fail_detail = str(failed_abort_actions[0].get("detail") or "unknown error")
                    abort_narration = (
                        f"{abort_narration} Notfall-Oeffnung fehlgeschlagen: {fail_detail}. Session bleibt aktiv bis Oeffnung erfolgreich ist."
                        if request_lang == "de"
                        else f"{abort_narration} Emergency opening failed: {fail_detail}. Session remains active until opening succeeds."
                    )
            else:
                # Abort was cancelled - clear any existing abort_decision pending actions
                existing_pending_actions = [
                    action
                    for action in existing_pending_actions
                    if _normalize_action_type(str((action or {}).get("action_type") or "")) != "abort_decision"
                ]

        if abort_handled:
            narration = abort_narration or timer_narration or ""
        elif timer_narration and explicit_intent_action is None:
            narration = timer_narration
        else:
            narration_raw = generate_ai_narration_for_session(
                db, request, session, action_text, request_lang, payload.attachments
            )
            narration, ai_pending_actions, generated_files = extract_pending_actions(narration_raw)
            # If user uploaded images, filter out ALL image_verification actions
            # (images are for LLM review/context only, not verification requests)
            # If no images uploaded, keep only the first image_verification (deduplicate)
            has_image_attachments = any(
                str(item.get("type", "")).startswith("image/")
                for item in (payload.attachments or [])
            )
            if has_image_attachments:
                # User uploaded images → filter out ALL image_verification requests
                ai_pending_actions = [
                    action
                    for action in ai_pending_actions
                    if _normalize_action_type(str((action or {}).get("action_type") or "")) != "image_verification"
                ]
            else:
                # No image uploads → deduplicate image_verification (keep only first)
                seen_image_verification = False
                deduplicated_actions = []
                for action in ai_pending_actions:
                    action_type = _normalize_action_type(str((action or {}).get("action_type") or ""))
                    if action_type == "image_verification":
                        if not seen_image_verification:
                            deduplicated_actions.append(action)
                            seen_image_verification = True
                        # else: skip duplicate image_verification
                    else:
                        deduplicated_actions.append(action)
                ai_pending_actions = deduplicated_actions
            precheck_failed_actions: list[dict] = []
            raw_has_machine_tag = bool(re.search(r"\[\[(REQUEST|ACTION):", narration_raw, flags=re.IGNORECASE))
            if not ai_pending_actions:
                reask_attempted = True
                repaired_actions, repaired = _repair_missing_request_tag(
                    db=db,
                    request=request,
                    session=session,
                    request_lang=request_lang,
                    user_message=action_text,
                    narration_raw=narration_raw,
                )
                if repaired:
                    ai_pending_actions = repaired_actions
                    reask_applied = True
                    precheck_failed_actions.append(
                        {
                            "action_type": str(ai_pending_actions[0].get("action_type") or ""),
                            "payload": ai_pending_actions[0].get("payload") or {},
                            "detail": "LLM repair round generated structured action tag.",
                            "severity": "info",
                        }
                    )
            if not ai_pending_actions:
                fallback_action = explicit_intent_action or _fallback_pending_action_from_user_intent(action_text, policy)
                if fallback_action is not None:
                    if strict_request_tag_mode:
                        if explicit_intent_action is not None and timer_pending:
                            ai_pending_actions = [fallback_action]
                            fallback_applied = True
                            precheck_failed_actions.append(
                                {
                                    "action_type": str(fallback_action.get("action_type") or ""),
                                    "payload": fallback_action.get("payload") or {},
                                    "detail": "Applied explicit user-intent fallback while timer-expiry state was active.",
                                    "severity": "info",
                                }
                            )
                        else:
                            precheck_failed_actions.append(
                                {
                                    "action_type": str(fallback_action.get("action_type") or ""),
                                    "payload": fallback_action.get("payload") or {},
                                    "detail": (
                                        "Strict request-tag mode: no valid structured action tag after repair; "
                                        "action not executed."
                                    ),
                                    "severity": "error",
                                }
                            )
                    else:
                        ai_pending_actions = [fallback_action]
                        fallback_applied = True
                        precheck_failed_actions.append(
                            {
                                "action_type": str(fallback_action.get("action_type") or ""),
                                "payload": fallback_action.get("payload") or {},
                                "detail": "LLM returned no structured action tag; applied user-intent fallback.",
                                "severity": "info",
                            }
                        )
            ai_pending_actions, executed_actions, auto_failed_actions, updated_policy = _auto_execute_pending_actions(
                request=request,
                policy=policy,
                pending_actions=ai_pending_actions,
            )
            failed_actions = [*precheck_failed_actions, *auto_failed_actions]
            policy = updated_policy
            # Merge existing pending_actions with new ai_pending_actions
            pending_actions.extend(existing_pending_actions)
            pending_actions.extend(ai_pending_actions)
            pending_actions = _dedupe_pending_actions(pending_actions)
            pending_actions = _keep_single_latest_image_verification_pending(pending_actions)
            if executed_actions:
                policy_dirty = True
            if raw_has_machine_tag:
                executed_action_types = [
                    str(item.get("action_type") or "").strip()
                    for item in executed_actions
                    if str(item.get("action_type") or "").strip()
                ]
                pending_action_types = [
                    str(action.get("action_type") or "").strip()
                    for action in pending_actions
                    if str(action.get("action_type") or "").strip()
                ]
                machine_tag_event = {
                    "event_type": "machine_tag_filtered",
                    "detail": "AI narration contained machine tags that were removed before returning the response.",
                    "metadata": {
                        "raw_machine_tag_present": True,
                        "raw_preview": narration_raw[:400],
                        "fallback_applied": fallback_applied,
                        "reask_applied": reask_applied,
                        "executed_action_types": executed_action_types,
                        "pending_action_types": pending_action_types,
                        "pending_actions_count": len(pending_actions),
                        "failed_actions_count": len(failed_actions),
                    },
                }
                audit_events_to_log.append(machine_tag_event)

        if policy_dirty:
            session.policy_snapshot_json = json.dumps(policy)

        activity_snapshot_event = {
            "event_type": "activity_snapshot",
            "detail": "Action status snapshot captured for this turn.",
            "metadata": {
                "source": "chat_turn",
                "pending_actions": pending_actions,
                "executed_actions": executed_actions,
                "failed_actions": failed_actions,
                "action_diagnostics": {
                    "strict_request_tag_mode": strict_request_tag_mode,
                    "raw_machine_tag_present": raw_has_machine_tag,
                    "reask_attempted": reask_attempted,
                    "reask_applied": reask_applied,
                    "fallback_applied": fallback_applied,
                },
            },
        }
        audit_events_to_log.append(activity_snapshot_event)

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
        db.flush()
        refresh_session_roleplay_state(db, session, pending_audit_events=audit_events_to_log)
        db.add(session)
        if audit_events_to_log:
            for event in audit_events_to_log:
                record_audit_event(
                    db=db,
                    session_id=session.id,
                    user_id=session.user_id,
                    turn_id=turn.id,
                    event_type=event.get("event_type") or "",
                    detail=event.get("detail") or "",
                    metadata=event.get("metadata"),
                )
        db.commit()
        pending_rows = _collect_pending_actions_for_session(db, session.id)
        pending_actions = _with_action_ids_from_pending_rows(pending_actions, pending_rows)
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
        "action_diagnostics": {
            "strict_request_tag_mode": strict_request_tag_mode,
            "raw_machine_tag_present": raw_has_machine_tag,
            "reask_attempted": reask_attempted,
            "reask_applied": reask_applied,
            "fallback_applied": fallback_applied,
            "pending_actions_count": len(pending_actions),
            "failed_actions_count": len(failed_actions),
        },
        "next_state": "awaiting_wearer_action",
    }


@router.post("/vision-review")
def chat_vision_review(payload: ChatVisionReviewRequest, request: Request) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    request_lang = lang(payload.language)
    prompt = payload.message.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")
    content_type = payload.picture_content_type.lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="picture_content_type must be image/*")
    logger.info(f"[ImageVerification] Received vision-review request for session {payload.session_id}")
    logger.info(f"[ImageVerification] - Picture name: {payload.picture_name}")
    logger.info(f"[ImageVerification] - Content type: {content_type}")
    logger.info(f"[ImageVerification] - DataURL length: {len(payload.picture_data_url)} chars")
    logger.info(f"[ImageVerification] - DataURL prefix: {payload.picture_data_url[:100]}")
    if not payload.picture_data_url.startswith(f"data:{content_type};base64,"):
        raise HTTPException(status_code=400, detail="Invalid picture_data_url format.")
    image_b64 = payload.picture_data_url.split(",", 1)[1]
    logger.info(f"[ImageVerification] - Base64 length: {len(image_b64)} chars")
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc
    logger.info(f"[ImageVerification] - Decoded image size: {len(image_bytes)} bytes")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="picture too large (max 8MB)")
    # Validate actual image content by checking magic bytes
    _IMAGE_MAGIC = {
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"RIFF": "image/webp",  # WebP starts with RIFF....WEBP
        b"GIF87a": "image/gif",
        b"GIF89a": "image/gif",
    }
    detected_type = None
    for magic, mime in _IMAGE_MAGIC.items():
        if image_bytes[:len(magic)] == magic:
            detected_type = mime
            break
    if detected_type is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a recognized image format.")
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
            "Return only the verification evaluation. "
            "Do not include a separate image description section. "
            "No greeting and no roleplay framing. "
            "Keep it concise (max 4 short sentences) and include explicit pass/fail with reason."
        )
    if action_payload:
        enriched_prompt = f"{enriched_prompt}\n\nVerification payload: {action_payload_json}"
    enriched_prompt = f"{enriched_prompt}\n\nImage source: {payload.source}"
    enriched_prompt = (
        f"{enriched_prompt}\n\n"
        "Output format requirement: Provide only a concise verification result (no standalone image description), "
        "max 4 short sentences, ending with a clear verdict: PASSED or FAILED."
    )
    enriched_prompt = (
        f"{enriched_prompt}\n"
        "Do not output any machine tags such as [[REQUEST:...]], [[ACTION:...]], [REQUEST:...], or [Suggest:...]."
    )

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        audit_events_to_log: list[dict] = []
        narration_raw = generate_ai_narration_for_session(
            db, request, session, enriched_prompt, request_lang, attachments
        )
        narration, new_pending_actions, generated_files = extract_pending_actions(narration_raw)
        # Filter out any image_verification actions from new_pending_actions
        # (vision-review should not trigger new verification requests)
        new_pending_actions = [
            action
            for action in new_pending_actions
            if _normalize_action_type(str((action or {}).get("action_type") or "")) != "image_verification"
        ]
        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        # Load existing pending_actions from the latest activity_snapshot
        existing_pending_actions = _load_latest_pending_actions(db, payload.session_id)
        new_pending_actions, executed_actions, failed_actions, updated_policy = _auto_execute_pending_actions(
            request=request,
            policy=policy,
            pending_actions=new_pending_actions,
        )
        verification_status = _extract_verification_status(narration)
        verification_payload = {
            **action_payload,
            "source": payload.source,
            "stored_image_path": saved_image_path,
        }
        if verification_status == "failed":
            # Clear resolved image_verification from both existing and new pending_actions
            existing_pending_actions = _clear_resolved_image_verification_pending(
                existing_pending_actions, verification_payload
            )
            new_pending_actions = _clear_resolved_image_verification_pending(
                new_pending_actions, verification_payload
            )
            failed_actions.append(
                {
                    "action_type": "image_verification",
                    "payload": verification_payload,
                    "detail": "Image verification verdict: FAILED.",
                }
            )
        elif verification_status == "success":
            # Clear resolved image_verification from both existing and new pending_actions
            existing_pending_actions = _clear_resolved_image_verification_pending(
                existing_pending_actions, verification_payload
            )
            new_pending_actions = _clear_resolved_image_verification_pending(
                new_pending_actions, verification_payload
            )
            executed_actions.append(
                {
                    "action_type": "image_verification",
                    "payload": verification_payload,
                    "message": "Image verification verdict: PASSED.",
                }
            )
        # Merge existing (minus resolved) + new pending_actions
        pending_actions = _dedupe_pending_actions(existing_pending_actions + new_pending_actions)
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
        audit_events_to_log.append(
            {
                "event_type": "activity_snapshot",
                "detail": "Action status snapshot captured for this vision review turn.",
                "metadata": {
                    "source": "chat_vision_review",
                    "pending_actions": pending_actions,
                    "executed_actions": executed_actions,
                    "failed_actions": failed_actions,
                },
            }
        )
        db.add(turn)
        db.flush()
        refresh_session_roleplay_state(db, session, pending_audit_events=audit_events_to_log)
        db.add(session)
        for event in audit_events_to_log:
            record_audit_event(
                db=db,
                session_id=session.id,
                user_id=session.user_id,
                turn_id=turn.id,
                event_type=event.get("event_type") or "",
                detail=event.get("detail") or "",
                metadata=event.get("metadata"),
            )
        db.commit()
        pending_rows = _collect_pending_actions_for_session(db, session.id)
        pending_actions = _with_action_ids_from_pending_rows(pending_actions, pending_rows)
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
        record_audit_event(
            db=db,
            session_id=session.id,
            user_id=session.user_id,
            turn_id=None,
            event_type="activity_manual_execute",
            detail="Manual action execution completed.",
            metadata={
                "source": "chat_action_execute",
                "status": "success",
                "action_id": payload.action_id,
                "action_type": result.get("action_type"),
                "payload": payload.payload or {},
                "result_payload": result.get("payload") or {},
                "message": result.get("message") or "",
                "chaster": result.get("chaster"),
            },
        )
        refresh_session_roleplay_state(db, session, recent_action_types=[normalized_action])
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
        "chaster": result.get("chaster"),
        "message": result["message"],
    }


@router.get("/pending/{session_id}")
def get_pending_actions(
    session_id: str,
    request: Request,
    auth_token: str | None = None,
    ai_access_token: str | None = None,
) -> dict:
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        if ai_access_token and str(ai_access_token).strip():
            expected_ai_token = str(os.getenv("AI_SESSION_READ_TOKEN") or "").strip()
            if not expected_ai_token or expected_ai_token != str(ai_access_token).strip():
                raise HTTPException(status_code=401, detail="Invalid AI access token.")
        else:
            user_id = resolve_user_id_from_token(str(auth_token or "").strip(), request)
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid auth token.")
            if session.user_id != user_id:
                raise HTTPException(status_code=403, detail="Session does not belong to user.")

        pending_actions = _collect_pending_actions_for_session(db, session_id)
        return {
            "session_id": session_id,
            "total": len(pending_actions),
            "pending_actions": pending_actions,
        }
    finally:
        db.close()


@router.post("/actions/resolve")
def chat_action_resolve(payload: ChatActionResolveRequest, request: Request) -> dict:
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        if payload.expected_status != "pending":
            raise HTTPException(status_code=409, detail="Only pending actions can be resolved.")

        pending_actions = _collect_pending_actions_for_session(db, payload.session_id)
        target = next((item for item in pending_actions if item.get("action_id") == payload.action_id), None)
        if target is None:
            raise HTTPException(status_code=409, detail="Pending action no longer exists or was already resolved.")

        resolution_message = str(payload.note or "").strip()
        if not resolution_message:
            if payload.resolution_status == "success":
                resolution_message = "Pending action manually marked as successful."
            elif payload.resolution_status == "canceled":
                resolution_message = "Pending action was canceled."
            else:
                resolution_message = "Pending action manually marked as failed."

        record_audit_event(
            db=db,
            session_id=session.id,
            user_id=session.user_id,
            turn_id=target.get("turn_id"),
            event_type="activity_manual_resolve",
            detail="Manual pending action resolution recorded.",
            metadata={
                "source": "chat_action_resolve",
                "status": payload.resolution_status,
                "expected_status": payload.expected_status,
                "action_id": target.get("action_id"),
                "action_type": target.get("action_type"),
                "payload": target.get("payload") or {},
                "message": resolution_message,
                "event_id": target.get("event_id"),
                "turn_no": target.get("turn_no"),
            },
        )
        db.commit()
        return {
            "resolved": True,
            "session_id": payload.session_id,
            "action_id": target.get("action_id"),
            "status": payload.resolution_status,
            "message": resolution_message,
        }
    finally:
        db.close()

@router.get("/seal/{session_id}")
def get_seal_status(session_id: str, request: Request, ai_access_token: str | None = None) -> dict:
    """
    Retrieve current seal/plomb status for a session.
    
    Response includes:
    - seal_mode: "none", "plomben", or "versiegelung"
    - runtime_seal: current status, text (number), and renewal status
    
    Requires AI access token for authentication.
    """
    if not ai_access_token or not str(ai_access_token).strip():
        raise HTTPException(status_code=401, detail="AI access token required.")
    
    ai_token = str(os.getenv("AI_SESSION_READ_TOKEN") or "").strip()
    if not ai_token or ai_token != str(ai_access_token).strip():
        raise HTTPException(status_code=401, detail="Invalid AI access token.")
    
    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        
        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        
        seal_cfg = policy.get("seal", {}) if isinstance(policy.get("seal"), dict) else {}
        seal_mode = str(seal_cfg.get("mode") or "none").strip().lower()
        runtime_seal = policy.get("runtime_seal", {}) if isinstance(policy.get("runtime_seal"), dict) else {}
        
        return {
            "session_id": session_id,
            "seal_mode": seal_mode,
            "runtime_seal": {
                "status": runtime_seal.get("status"),
                "current_text": runtime_seal.get("current_text"),
                "sealed_at": runtime_seal.get("sealed_at"),
                "broken_at": runtime_seal.get("broken_at"),
                "needs_new_seal": bool(runtime_seal.get("needs_new_seal", False)),
            } if seal_mode != "none" else None,
        }
    finally:
        db.close()
