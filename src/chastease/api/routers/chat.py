import base64
import json
import logging
import os
import re
import time
import unicodedata
from pathlib import Path
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from chastease.api.runtime import find_setup_session_id_for_active_session, get_db_session, lang
from chastease.api.schemas import ChatActionExecuteRequest, ChatTurnRequest, ChatVisionReviewRequest
from chastease.models import ChastitySession, Turn
from chastease.repositories.setup_store import load_sessions, save_sessions
from chastease.services.narration import extract_pending_actions, generate_ai_narration_for_session
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
    if bool(policy.get("runtime_timer_expiry_open_prompted")):
        return None, [], policy
    policy["runtime_timer_expiry_open_prompted"] = True
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

        if abort_handled:
            narration = abort_narration or timer_narration or ""
        elif timer_narration:
            narration = timer_narration
        else:
            narration_raw = generate_ai_narration_for_session(
                db, request, session, action_text, request_lang, payload.attachments
            )
            narration, ai_pending_actions, generated_files = extract_pending_actions(narration_raw)
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
                        }
                    )
            if not ai_pending_actions:
                fallback_action = _fallback_pending_action_from_user_intent(action_text, policy)
                if fallback_action is not None:
                    if strict_request_tag_mode:
                        precheck_failed_actions.append(
                            {
                                "action_type": str(fallback_action.get("action_type") or ""),
                                "payload": fallback_action.get("payload") or {},
                                "detail": (
                                    "Strict request-tag mode: no valid structured action tag after repair; "
                                    "action not executed."
                                ),
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
                            }
                        )
            ai_pending_actions, executed_actions, auto_failed_actions, updated_policy = _auto_execute_pending_actions(
                request=request,
                policy=policy,
                pending_actions=ai_pending_actions,
            )
            failed_actions = [*precheck_failed_actions, *auto_failed_actions]
            policy = updated_policy
            pending_actions.extend(ai_pending_actions)
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
        narration, pending_actions, generated_files = extract_pending_actions(narration_raw)
        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        if not isinstance(policy, dict):
            policy = {}
        pending_actions, executed_actions, failed_actions, updated_policy = _auto_execute_pending_actions(
            request=request,
            policy=policy,
            pending_actions=pending_actions,
        )
        verification_status = _extract_verification_status(narration)
        verification_payload = {
            **action_payload,
            "source": payload.source,
            "stored_image_path": saved_image_path,
        }
        if verification_status == "failed":
            failed_actions.append(
                {
                    "action_type": "image_verification",
                    "payload": verification_payload,
                    "detail": "Image verification verdict: FAILED.",
                }
            )
        elif verification_status == "success":
            executed_actions.append(
                {
                    "action_type": "image_verification",
                    "payload": verification_payload,
                    "message": "Image verification verdict: PASSED.",
                }
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
                "action_type": result.get("action_type"),
                "payload": result.get("payload") or {},
                "message": result.get("message") or "",
            },
        )
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
