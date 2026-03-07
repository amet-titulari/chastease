import asyncio
import json
from datetime import UTC, date, datetime
import re
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from chastease.api.questionnaire import QUESTION_BANK, QUESTION_IDS, QUESTIONNAIRE_VERSION, TRAIT_KEYS
from chastease.api.schemas import (
    SetupAICalibrationTurnRequest,
    PsychogramRecalibrationRequest,
    SetupAIControlledFieldsUpdateRequest,
    SetupAnswersRequest,
    SetupArtifactsRequest,
    SetupChatPreviewRequest,
    SetupContractConsentRequest,
    SetupIntegrationsUpdateRequest,
    SetupSealUpdateRequest,
    SetupStartRequest,
)
from chastease.models import Character, ChastitySession, Turn, User
from chastease.api.setup_domain import (
    _build_policy,
    _build_psychogram,
    _create_draft_setup_session,
    _ensure_generated_contract_consent,
    _find_user_setup_session,
    _get_session_or_404,
    _lang,
    _localized_questions,
    _normalize_consent_for_compare,
    _now_iso,
    _psychogram_brief,
    _render_contract_with_consent,
    _required_contract_consent_text,
    _resolve_contract_dates,
    _t,
    _validate_answer,
    _validate_safety_answers,
    get_ai_controlled_session_fields,
    get_ai_controlled_policy_fields,
    get_ai_controlled_psychogram_traits,
)
from chastease.repositories.setup_store import load_sessions, save_sessions
from chastease.api.setup_ai import (
    extract_pending_actions,
    generate_ai_narration_for_setup_preview,
    generate_contract_for_setup,
    generate_psychogram_analysis_with_end_date_for_setup,
)
from chastease.api.setup_infra import (
    get_db_session,
    resolve_user_id_from_token,
    sync_setup_snapshot_to_active_session,
    sync_setup_snapshot_to_active_session_db,
)
from chastease.api.routers.chaster import (
    ChasterCreateSessionRequest,
    chaster_has_any_credentials,
    create_chaster_session,
)
from chastease.shared.audit import record_audit_event

router = APIRouter(prefix="/setup", tags=["setup"])

CALIBRATION_INTENSITY_TO_SCALE = {
    "low": 20,
    "medium": 45,
    "strong": 75,
    "demanding": 95,
}

CALIBRATION_FIELDS = {"instruction_style", "desired_intensity", "grooming_preference", "escalation_mode"}


def _is_llm_timeout_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "timeout at" in text or "provider timeout" in text


def _consent_technical_info(setup_session: dict) -> dict:
    consent = (
        (((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("consent"))
        or {}
    )
    return {
        "required_text": str(consent.get("required_text") or _required_contract_consent_text(setup_session.get("language", "de"))),
        "accepted": bool(consent.get("accepted")),
        "consent_text": str(consent.get("consent_text") or "") or None,
        "accepted_at": str(consent.get("accepted_at") or "") or None,
    }


def _validate_ttlock_config(integrations: list[str], integration_config: dict[str, dict[str, Any]]) -> None:
    normalized_integrations = [str(item).strip().lower() for item in (integrations or []) if str(item).strip()]
    if "ttlock" not in normalized_integrations:
        return
    # If no integration_config was provided for ttlock, allow starting setup
    # with ttlock listed in integrations; only validate when a ttlock
    # configuration object is actually supplied.
    if not isinstance(integration_config, dict) or "ttlock" not in integration_config:
        return
    ttlock_cfg = integration_config.get("ttlock")
    if not isinstance(ttlock_cfg, dict):
        raise HTTPException(
            status_code=400,
            detail=(
                "TT-Lock integration requires integration_config.ttlock with "
                "ttl_user, ttl_pass_md5 and ttl_lock_id."
            ),
        )
    ttl_user = str(ttlock_cfg.get("ttl_user") or "").strip()
    ttl_pass_md5 = str(ttlock_cfg.get("ttl_pass_md5") or "").strip().lower()
    ttl_lock_id = str(ttlock_cfg.get("ttl_lock_id") or "").strip()
    if not ttl_user or not ttl_pass_md5 or not ttl_lock_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "TT-Lock integration requires ttl_user, ttl_pass_md5 and ttl_lock_id "
                "in integration_config.ttlock."
            ),
        )
    if re.fullmatch(r"[0-9a-f]{32}", ttl_pass_md5) is None:
        raise HTTPException(
            status_code=400,
            detail="integration_config.ttlock.ttl_pass_md5 must be a lowercase 32-char md5 hex string.",
        )


def _validate_chaster_config(integrations: list[str], integration_config: dict[str, dict[str, Any]]) -> None:
    normalized_integrations = [str(item).strip().lower() for item in (integrations or []) if str(item).strip()]
    if "chaster" not in normalized_integrations:
        return
    if not isinstance(integration_config, dict) or "chaster" not in integration_config:
        return
    chaster_cfg = integration_config.get("chaster")
    if not isinstance(chaster_cfg, dict):
        raise HTTPException(
            status_code=400,
            detail="Chaster integration requires integration_config.chaster object.",
        )
    if not chaster_has_any_credentials(chaster_cfg):
        raise HTTPException(
            status_code=400,
            detail="integration_config.chaster requires credentials (OAuth2 or api_token).",
        )


def _latest_ttlock_seed_from_user_session(db, user_id: str) -> dict | None:
    latest_session = db.scalar(
        select(ChastitySession)
        .where(ChastitySession.user_id == user_id)
        .order_by(ChastitySession.updated_at.desc())
    )
    if latest_session is None:
        return None
    if not latest_session.policy_snapshot_json:
        return None
    try:
        policy = json.loads(latest_session.policy_snapshot_json)
    except Exception:
        return None
    if not isinstance(policy, dict):
        return None

    integration_config = policy.get("integration_config") if isinstance(policy.get("integration_config"), dict) else {}
    ttlock_cfg = integration_config.get("ttlock") if isinstance(integration_config.get("ttlock"), dict) else None
    if ttlock_cfg is None:
        return None

    ttl_user = str(ttlock_cfg.get("ttl_user") or "").strip()
    ttl_pass_md5 = str(ttlock_cfg.get("ttl_pass_md5") or "").strip().lower()
    ttl_lock_id = str(ttlock_cfg.get("ttl_lock_id") or "").strip()
    ttl_gateway_id = str(ttlock_cfg.get("ttl_gateway_id") or "").strip()
    if not ttl_user or not ttl_pass_md5 or not ttl_lock_id:
        return None
    if re.fullmatch(r"[0-9a-f]{32}", ttl_pass_md5) is None:
        return None

    normalized_integrations = [
        str(item).strip().lower() for item in (policy.get("integrations") or []) if str(item).strip()
    ]
    if "ttlock" not in normalized_integrations:
        normalized_integrations.append("ttlock")

    result_cfg = {
        "ttl_user": ttl_user,
        "ttl_pass_md5": ttl_pass_md5,
        "ttl_lock_id": ttl_lock_id,
    }
    if ttl_gateway_id:
        result_cfg["ttl_gateway_id"] = ttl_gateway_id

    return {
        "integrations": normalized_integrations,
        "ttlock": result_cfg,
    }


def _system_note(lang: str, key: str, **kwargs) -> str:
    if key == "psychogram_ready":
        end_date = kwargs.get("end_date") or ("KI-entscheidet" if lang == "de" else "AI-decides")
        return (
            f"System-Hinweis: Psychogramm-Analyse erstellt. Vorlaeufiges Enddatum: {end_date}."
            if lang == "de"
            else f"System note: Psychogram analysis generated. Provisional end date: {end_date}."
        )
    if key == "contract_ready":
        return (
            "System-Hinweis: Vertragsentwurf wurde generiert."
            if lang == "de"
            else "System note: Contract draft has been generated."
        )
    if key == "artifacts_ready":
        end_date = kwargs.get("end_date") or ("KI-entscheidet" if lang == "de" else "AI-decides")
        return (
            f"System-Hinweis: Psychogramm-Analyse und Vertragsentwurf wurden generiert. Vorlaeufiges Enddatum: {end_date}."
            if lang == "de"
            else f"System note: Psychogram analysis and contract draft generated. Provisional end date: {end_date}."
        )
    if key == "consent_done":
        accepted_at = kwargs.get("accepted_at") or "-"
        return (
            f"System-Hinweis: Digital Consent wurde erteilt ({accepted_at})."
            if lang == "de"
            else f"System note: Digital consent granted ({accepted_at})."
        )
    return "System note."


def _desired_intensity_to_scale_100(choice: str) -> int:
    normalized = str(choice or "").strip().lower()
    mapping = {
        "low": 20,
        "medium": 45,
        "strong": 75,
        "demanding": 95,
    }
    return mapping.get(normalized, 45)


def _extract_json_payload(raw: str) -> dict | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(fenced)
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _next_calibration_question(inferred: dict[str, str], lang: str) -> str:
    missing = CALIBRATION_FIELDS - set(inferred.keys())
    if "instruction_style" in missing:
        return (
            "Wie soll ich dich am liebsten anleiten: direkt, höflich-autoritär, suggestiv oder gemischt?"
            if lang == "de"
            else "How should I guide you: direct, polite-authoritative, suggestive, or mixed?"
        )
    if "desired_intensity" in missing:
        return (
            "Welche Intensität passt aktuell: niedrig, mittel, stark oder belastend?"
            if lang == "de"
            else "Which intensity fits right now: low, medium, strong, or demanding?"
        )
    if "escalation_mode" in missing:
        return (
            "Wie schnell soll die Eskalation sein: sehr langsam, langsam, moderat, stark oder aggressiv?"
            if lang == "de"
            else "How fast should escalation be: very slow, slow, moderate, strong, or aggressive?"
        )
    if "grooming_preference" in missing:
        return (
            "Welche Intimrasur-Präferenz soll gelten: keine Präferenz, glatt rasiert, getrimmt oder natürlich?"
            if lang == "de"
            else "Which grooming preference should apply: no preference, clean shaven, trimmed, or natural?"
        )
    return (
        "Danke. Ich habe die Kalibrierung abgeschlossen. Möchtest du noch etwas präzisieren?"
        if lang == "de"
        else "Thanks, calibration is complete. Do you want to fine-tune anything else?"
    )


def _infer_calibration_from_text(message: str, previous: dict[str, str]) -> dict[str, str]:
    text = str(message or "").strip().lower()
    inferred = dict(previous)
    if not text:
        return inferred

    if any(token in text for token in ["direkt", "befehl", "command"]):
        inferred["instruction_style"] = "direct_command"
    elif any(token in text for token in ["höflich", "hoeflich", "autorit", "polite"]):
        inferred["instruction_style"] = "polite_authoritative"
    elif any(token in text for token in ["suggestiv", "verführer", "verfuehrer", "seductive", "suggestive"]):
        inferred["instruction_style"] = "suggestive"
    elif "gemischt" in text or "mixed" in text:
        inferred["instruction_style"] = "mixed"

    if any(token in text for token in ["niedrig", "sanft", "low", "gentle"]):
        inferred["desired_intensity"] = "low"
    elif any(token in text for token in ["mittel", "medium", "moderat"]):
        inferred["desired_intensity"] = "medium"
    elif any(token in text for token in ["stark", "intens", "strong"]):
        inferred["desired_intensity"] = "strong"
    elif any(token in text for token in ["belastend", "fordernd", "demanding", "hardcore"]):
        inferred["desired_intensity"] = "demanding"

    if any(token in text for token in ["sehr langsam", "very slow"]):
        inferred["escalation_mode"] = "very_slow"
    elif any(token in text for token in ["langsam", "slow"]):
        inferred["escalation_mode"] = "slow"
    elif any(token in text for token in ["moderat", "mittel", "moderate"]):
        inferred["escalation_mode"] = "moderate"
    elif any(token in text for token in ["aggressiv", "aggressive"]):
        inferred["escalation_mode"] = "aggressive"
    elif any(token in text for token in ["stark", "strong"]):
        inferred["escalation_mode"] = "strong"

    if any(token in text for token in ["keine präferenz", "keine praeferenz", "no preference"]):
        inferred["grooming_preference"] = "no_preference"
    elif any(token in text for token in ["glatt", "clean shaven", "rasiert"]):
        inferred["grooming_preference"] = "clean_shaven"
    elif any(token in text for token in ["trim", "getrimmt"]):
        inferred["grooming_preference"] = "trimmed"
    elif any(token in text for token in ["natürlich", "natuerlich", "natural"]):
        inferred["grooming_preference"] = "natural"

    return inferred


def _sanitize_inferred_calibration(payload: dict[str, Any], current: dict[str, str]) -> tuple[dict[str, str], float, bool]:
    inferred = dict(current)
    raw_inferred = payload.get("inferred")
    if isinstance(raw_inferred, dict):
        for key in CALIBRATION_FIELDS:
            if key not in raw_inferred:
                continue
            val = str(raw_inferred.get(key) or "").strip()
            if not val:
                continue
            inferred[key] = val

    valid_sets = {
        "instruction_style": {"direct_command", "polite_authoritative", "suggestive", "mixed"},
        "desired_intensity": {"low", "medium", "strong", "demanding"},
        "grooming_preference": {"no_preference", "clean_shaven", "trimmed", "natural"},
        "escalation_mode": {"very_slow", "slow", "moderate", "strong", "aggressive"},
    }
    for key, allowed in valid_sets.items():
        if key in inferred and inferred[key] not in allowed:
            inferred.pop(key, None)

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))
    completed = bool(payload.get("completed")) or (
        len(CALIBRATION_FIELDS - set(inferred.keys())) == 0 and confidence >= 0.75
    )
    return inferred, confidence, completed


def _apply_calibration_to_setup(setup_session: dict, inferred: dict[str, str], now_iso: str) -> dict[str, str]:
    changed: dict[str, str] = {}
    if "instruction_style" in inferred and setup_session.get("instruction_style") != inferred["instruction_style"]:
        setup_session["instruction_style"] = inferred["instruction_style"]
        changed["instruction_style"] = inferred["instruction_style"]
    if "desired_intensity" in inferred and setup_session.get("desired_intensity") != inferred["desired_intensity"]:
        setup_session["desired_intensity"] = inferred["desired_intensity"]
        changed["desired_intensity"] = inferred["desired_intensity"]
    if "grooming_preference" in inferred and setup_session.get("grooming_preference") != inferred["grooming_preference"]:
        setup_session["grooming_preference"] = inferred["grooming_preference"]
        changed["grooming_preference"] = inferred["grooming_preference"]
    if "escalation_mode" in inferred and setup_session.get("escalation_mode") != inferred["escalation_mode"]:
        setup_session["escalation_mode"] = inferred["escalation_mode"]
        changed["escalation_mode"] = inferred["escalation_mode"]

    answers_by_question = {
        str(entry.get("question_id")): entry.get("value")
        for entry in (setup_session.get("answers") or [])
        if isinstance(entry, dict) and str(entry.get("question_id") or "").strip()
    }
    if "instruction_style" in inferred:
        answers_by_question["q8_instruction_style"] = inferred["instruction_style"]
    if "grooming_preference" in inferred:
        answers_by_question["q12_grooming_preference"] = inferred["grooming_preference"]
    if "desired_intensity" in inferred:
        answers_by_question["q6_intensity_1_5"] = _desired_intensity_to_scale_100(inferred["desired_intensity"])
    if "escalation_mode" in inferred:
        answers_by_question["q11_escalation_mode"] = inferred["escalation_mode"]
    setup_session["answers"] = [
        {"question_id": question_id, "value": value}
        for question_id, value in answers_by_question.items()
    ]

    setup_session["psychogram"] = _build_psychogram(setup_session)
    setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])
    setup_session["updated_at"] = now_iso
    return changed


def _ensure_active_session_from_setup(db, setup_session: dict) -> str:
    existing_id = str(setup_session.get("active_session_id") or "").strip()
    if existing_id:
        existing = db.get(ChastitySession, existing_id)
        if existing is not None:
            return existing_id
    session_id = str(uuid4())
    
    # Prepare policy with initial seal number if configured
    policy = setup_session.get("policy_preview") or {}
    if isinstance(policy, dict):
        policy = dict(policy)  # Make a copy
        seal_config = policy.get("seal", {})
        seal_mode = seal_config.get("mode", "none")
        initial_seal_number = setup_session.get("initial_seal_number")
        
        # Initialize runtime_seal with initial seal number if seal mode is active
        if seal_mode in {"plomben", "versiegelung"} and initial_seal_number:
            policy["runtime_seal"] = {
                "status": "sealed",
                "current_text": initial_seal_number,
                "sealed_at": datetime.now(UTC).isoformat(),
                "needs_new_seal": False
            }
    
    db_session = ChastitySession(
        id=session_id,
        user_id=setup_session["user_id"],
        character_id=setup_session.get("character_id"),
        status="active",
        language=setup_session["language"],
        policy_snapshot_json=json.dumps(policy),
        psychogram_snapshot_json=json.dumps(setup_session.get("psychogram") or {}),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(db_session)
    setup_session["active_session_id"] = session_id
    return session_id


def _maybe_create_chaster_session_on_contract_accept(
    setup_session: dict,
    user_id: str,
    auth_token: str,
    request: Request,
) -> dict | None:
    integrations = [
        str(item).strip().lower() for item in (setup_session.get("integrations") or []) if str(item).strip()
    ]
    if "chaster" not in integrations:
        return None

    integration_config = setup_session.get("integration_config") if isinstance(setup_session.get("integration_config"), dict) else {}
    chaster_cfg = integration_config.get("chaster") if isinstance(integration_config.get("chaster"), dict) else {}
    lock_id = str(chaster_cfg.get("lock_id") or "").strip()
    if lock_id:
        return None

    if not chaster_has_any_credentials(chaster_cfg):
        raise HTTPException(
            status_code=409,
            detail="Chaster is enabled but integration_config.chaster credentials are missing.",
        )

    min_duration = int(chaster_cfg.get("min_duration_minutes") or 60)
    max_duration = int(chaster_cfg.get("max_duration_minutes") or max(60, min_duration))
    if min_duration <= 0:
        min_duration = 60
    if max_duration < min_duration:
        max_duration = min_duration

    min_limit = int(chaster_cfg.get("min_limit_duration_minutes") or 0)
    max_limit = int(chaster_cfg.get("max_limit_duration_minutes") or 0)
    if min_limit < 0:
        min_limit = 0
    if max_limit < min_limit:
        max_limit = min_limit

    request_payload = ChasterCreateSessionRequest(
        user_id=user_id,
        auth_token=auth_token,
        chaster_api_token=str(chaster_cfg.get("api_token") or "").strip() or None,
        code=str(chaster_cfg.get("code") or "").strip() or None,
        min_duration_minutes=min_duration,
        max_duration_minutes=max_duration,
        min_limit_duration_minutes=min_limit,
        max_limit_duration_minutes=max_limit,
        display_remaining_time=bool(chaster_cfg.get("display_remaining_time", True)),
        limit_lock_time=bool(chaster_cfg.get("limit_lock_time", True)),
        allow_session_offer=bool(chaster_cfg.get("allow_session_offer", True)),
        is_test_lock=bool(chaster_cfg.get("is_test_lock", False)),
        hide_time_logs=bool(chaster_cfg.get("hide_time_logs", True)),
        extensions=chaster_cfg.get("extensions") if isinstance(chaster_cfg.get("extensions"), list) else [],
    )

    try:
        created = asyncio.run(create_chaster_session(request_payload, request))
    except HTTPException as exc:
        raise HTTPException(status_code=502, detail=f"Chaster session creation failed during contract acceptance: {exc.detail}") from exc

    created_cfg = (
        (created.get("integration_config") or {}).get("chaster")
        if isinstance(created, dict)
        else None
    )
    if not isinstance(created_cfg, dict):
        raise HTTPException(status_code=502, detail="Chaster session creation returned invalid integration_config.")

    merged_cfg = dict(chaster_cfg)
    merged_cfg.update(created_cfg)
    integration_config["chaster"] = merged_cfg
    setup_session["integration_config"] = integration_config
    if isinstance(setup_session.get("policy_preview"), dict):
        setup_session["policy_preview"]["integration_config"] = integration_config
    return created_cfg


@router.post("/sessions/{setup_session_id}/chat-preview")
def setup_chat_preview(setup_session_id: str, payload: SetupChatPreviewRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session["user_id"] != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if setup_session.get("psychogram") is None or setup_session.get("policy_preview") is None:
        raise HTTPException(status_code=400, detail="Submit questionnaire answers before chat preview.")

    lang = _lang(payload.language)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")
    action_text = message

    db = get_db_session(request)
    try:
        narration_raw = generate_ai_narration_for_setup_preview(
            db,
            request,
            payload.user_id,
            action_text,
            lang,
            setup_session["psychogram"],
            setup_session["policy_preview"],
            payload.attachments,
        )
    finally:
        db.close()
    narration, pending_actions, generated_files = extract_pending_actions(narration_raw)
    return {
        "result": "accepted_preview",
        "setup_session_id": setup_session_id,
        "narration": narration,
        "pending_actions": pending_actions,
        "generated_files": generated_files,
        "preview": True,
        "next_state": "awaiting_wearer_action",
    }


@router.post("/sessions/{setup_session_id}/ai-calibration-turn")
def ai_calibration_turn(setup_session_id: str, payload: SetupAICalibrationTurnRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if setup_session.get("status") not in {"setup_in_progress", "configured"}:
        raise HTTPException(status_code=409, detail="Setup session is not editable.")

    lang = _lang(setup_session.get("language", "de"))
    wearer_message = str(payload.wearer_message or "").strip()
    calibration = setup_session.setdefault("ai_calibration", {})
    turns = calibration.setdefault("turns", [])

    current_inferred = dict(calibration.get("inferred") or {})
    for key in CALIBRATION_FIELDS:
        val = str(setup_session.get(key) or "").strip()
        if val:
            current_inferred[key] = val

    assistant_message = ""
    next_question = _next_calibration_question(current_inferred, lang)
    confidence = float(calibration.get("confidence") or 0.0)
    completed = bool(calibration.get("completed"))

    if wearer_message:
        db = get_db_session(request)
        try:
            if setup_session.get("psychogram") is None:
                setup_session["psychogram"] = _build_psychogram(setup_session)
            if setup_session.get("policy_preview") is None:
                setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])

            instruction = (
                "You are calibrating a roleplay session setup. Return JSON only (no markdown) with exactly this shape: "
                "{\"assistant_message\":\"...\",\"next_question\":\"...\",\"inferred\":{\"instruction_style\":\"direct_command|polite_authoritative|suggestive|mixed\",\"desired_intensity\":\"low|medium|strong|demanding\",\"grooming_preference\":\"no_preference|clean_shaven|trimmed|natural\",\"escalation_mode\":\"very_slow|slow|moderate|strong|aggressive\"},\"confidence\":0.0,\"completed\":false}. "
                "Only set inferred keys when confidence is sufficient."
            ) if lang == "en" else (
                "Du kalibrierst ein Rollenspiel-Setup. Antworte nur als JSON (kein Markdown) mit exakt dieser Struktur: "
                "{\"assistant_message\":\"...\",\"next_question\":\"...\",\"inferred\":{\"instruction_style\":\"direct_command|polite_authoritative|suggestive|mixed\",\"desired_intensity\":\"low|medium|strong|demanding\",\"grooming_preference\":\"no_preference|clean_shaven|trimmed|natural\",\"escalation_mode\":\"very_slow|slow|moderate|strong|aggressive\"},\"confidence\":0.0,\"completed\":false}. "
                "Setze inferred-Felder nur, wenn du ausreichend sicher bist."
            )
            context_block = (
                f"{instruction}\n\n"
                f"CURRENT_INFERRED: {json.dumps(current_inferred, ensure_ascii=False)}\n"
                f"WEARER_MESSAGE: {wearer_message}\n"
                f"NEXT_FOCUS_QUESTION: {_next_calibration_question(current_inferred, lang)}"
            )
            raw = generate_ai_narration_for_setup_preview(
                db=db,
                request=request,
                user_id=payload.user_id,
                action=context_block,
                language=lang,
                psychogram=setup_session.get("psychogram") or {},
                policy=setup_session.get("policy_preview") or {},
            )
        finally:
            db.close()

        parsed = _extract_json_payload(raw) or {}
        ai_inferred, ai_confidence, ai_completed = _sanitize_inferred_calibration(parsed, current_inferred)
        fallback_inferred = _infer_calibration_from_text(wearer_message, ai_inferred)
        inferred = fallback_inferred
        confidence = max(ai_confidence, 0.25 if inferred != current_inferred else 0.0)
        completed = bool(ai_completed) or (len(CALIBRATION_FIELDS - set(inferred.keys())) == 0 and confidence >= 0.65)
        assistant_message = str(parsed.get("assistant_message") or "").strip() or (
            "Verstanden. Ich kalibriere die Werte auf Basis deiner Antwort." if lang == "de"
            else "Understood. I am calibrating values based on your answer."
        )
        next_question = str(parsed.get("next_question") or "").strip() or _next_calibration_question(inferred, lang)

        now = _now_iso()
        changed = _apply_calibration_to_setup(setup_session, inferred, now)
        calibration["inferred"] = inferred
        calibration["confidence"] = confidence
        calibration["completed"] = completed
        calibration["last_question"] = next_question
        turns.append(
            {
                "at": now,
                "wearer_message": wearer_message,
                "assistant_message": assistant_message,
                "next_question": next_question,
                "changed_fields": changed,
                "confidence": confidence,
            }
        )
        store[setup_session_id] = setup_session
        save_sessions(store)
        applied_to_active_session = sync_setup_snapshot_to_active_session(request, setup_session)
        return {
            "setup_session_id": setup_session_id,
            "assistant_message": assistant_message,
            "next_question": next_question,
            "inferred": inferred,
            "confidence": confidence,
            "completed": completed,
            "changed_fields": changed,
            "turns_count": len(turns),
            "applied_to_active_session": applied_to_active_session,
        }

    calibration["last_question"] = next_question
    calibration["inferred"] = current_inferred
    calibration["confidence"] = confidence
    calibration["completed"] = completed
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)
    return {
        "setup_session_id": setup_session_id,
        "assistant_message": (
            "Ich stelle dir jetzt ein paar gezielte Fragen für die Kalibrierung."
            if lang == "de"
            else "I will now ask a few targeted calibration questions."
        ),
        "next_question": next_question,
        "inferred": current_inferred,
        "confidence": confidence,
        "completed": completed,
        "turns_count": len(turns),
    }

@router.post("/sessions")
def start_setup_session(payload: SetupStartRequest, request: Request) -> dict:
    now = _now_iso()
    lang = _lang(payload.language)
    contract_start_date, contract_end_date, contract_min_end_date, contract_max_end_date = _resolve_contract_dates(
        payload.contract_start_date,
        payload.contract_end_date,
        payload.contract_min_end_date,
        payload.contract_max_end_date,
        payload.ai_controls_end_date,
    )
    opening_limit_period = payload.opening_limit_period
    max_openings_in_period = payload.max_openings_in_period
    if payload.max_openings_per_day is not None:
        opening_limit_period = "day"
        max_openings_in_period = payload.max_openings_per_day
    normalized_payload_integrations = [
        str(item).strip().lower() for item in (payload.integrations or []) if str(item).strip()
    ]
    payload_integration_config = payload.integration_config if isinstance(payload.integration_config, dict) else {}
    _validate_ttlock_config(normalized_payload_integrations, payload_integration_config)
    _validate_chaster_config(normalized_payload_integrations, payload_integration_config)
    latest_ttlock_seed = None
    db = get_db_session(request)
    try:
        token_user_id = resolve_user_id_from_token(payload.auth_token, request)
        if token_user_id != payload.user_id:
            raise HTTPException(status_code=401, detail="Invalid auth token for user.")
        user = db.get(User, payload.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
        if payload.character_id:
            character = db.get(Character, payload.character_id)
            if character is None or character.user_id != payload.user_id:
                raise HTTPException(status_code=400, detail="Invalid character_id for user.")
        active_session = db.scalar(
            select(ChastitySession)
            .where(ChastitySession.user_id == payload.user_id)
            .where(ChastitySession.status == "active")
            .order_by(ChastitySession.created_at.desc())
        )
        if active_session is not None:
            raise HTTPException(status_code=409, detail="Active session already exists.")
        latest_ttlock_seed = _latest_ttlock_seed_from_user_session(db, payload.user_id)
    finally:
        db.close()

    store = load_sessions()
    setup_session_id, setup_session = _find_user_setup_session(store, payload.user_id, {"draft", "setup_in_progress"})
    created_new_setup_session = False
    if setup_session is None:
        setup_session = _create_draft_setup_session(payload.user_id, lang)
        setup_session_id = setup_session["setup_session_id"]
        created_new_setup_session = True

    effective_integrations = list(normalized_payload_integrations)
    effective_integration_config = dict(payload_integration_config)
    has_ttlock_in_payload = isinstance(effective_integration_config.get("ttlock"), dict)
    existing_integration_config = setup_session.get("integration_config") if isinstance(setup_session.get("integration_config"), dict) else {}
    existing_has_ttlock = isinstance(existing_integration_config.get("ttlock"), dict)
    should_seed_ttlock = (
        not has_ttlock_in_payload
        and not existing_has_ttlock
        and isinstance(latest_ttlock_seed, dict)
        and setup_session.get("status") in {"draft", "setup_in_progress"}
    )
    if should_seed_ttlock:
        ttlock_seed = latest_ttlock_seed.get("ttlock") if isinstance(latest_ttlock_seed.get("ttlock"), dict) else None
        if ttlock_seed:
            effective_integration_config["ttlock"] = ttlock_seed
            if "ttlock" not in effective_integrations:
                effective_integrations.append("ttlock")

    setup_session.update(
        {
            "setup_session_id": setup_session_id,
            "user_id": payload.user_id,
            "user_display_name": str(user.display_name or "").strip() or payload.user_id,
            "character_id": payload.character_id,
            "status": "setup_in_progress",
            "hard_stop_enabled": payload.hard_stop_enabled,
            "autonomy_mode": payload.autonomy_mode,
            "seal_mode": payload.seal_mode,
            "initial_seal_number": payload.initial_seal_number,
            "integrations": effective_integrations,
            "integration_config": effective_integration_config,
            "language": lang,
            "blocked_trigger_words": payload.blocked_trigger_words,
            "forbidden_topics": payload.forbidden_topics,
            "contract_start_date": contract_start_date,
            "contract_end_date": contract_end_date,
            "contract_min_end_date": contract_min_end_date,
            "contract_max_end_date": contract_max_end_date,
            "ai_controls_end_date": payload.ai_controls_end_date,
            "max_penalty_per_day_minutes": payload.max_penalty_per_day_minutes,
            "max_penalty_per_week_minutes": payload.max_penalty_per_week_minutes,
            "opening_limit_period": opening_limit_period,
            "max_openings_in_period": max_openings_in_period,
            "max_openings_per_day": max_openings_in_period if opening_limit_period == "day" else 0,
            "opening_window_minutes": payload.opening_window_minutes,
            "instruction_style": payload.instruction_style,
            "desired_intensity": payload.desired_intensity,
            "grooming_preference": payload.grooming_preference,
            "escalation_mode": "moderate",
            "questionnaire_version": QUESTIONNAIRE_VERSION,
            "updated_at": now,
            "psychogram_analysis": None,
            "psychogram_analysis_status": "idle",
            "psychogram_analysis_generated_at": None,
            "contract_generation_status": "idle",
            "contract_generated_at": None,
            "ai_proposed_end_date": None,
            "ai_calibration": setup_session.get("ai_calibration") if isinstance(setup_session.get("ai_calibration"), dict) else {},
        }
    )
    if "created_at" not in setup_session:
        setup_session["created_at"] = now
    # keep previous answers to allow iterative setup editing without data loss
    setup_session.setdefault("answers", [])
    answers_by_question = {
        str(entry.get("question_id")): entry.get("value")
        for entry in (setup_session.get("answers") or [])
        if isinstance(entry, dict) and str(entry.get("question_id") or "").strip()
    }
    answers_by_question["q8_instruction_style"] = payload.instruction_style
    answers_by_question["q12_grooming_preference"] = payload.grooming_preference
    answers_by_question["q6_intensity_1_5"] = _desired_intensity_to_scale_100(payload.desired_intensity)
    setup_session["answers"] = [
        {"question_id": question_id, "value": value}
        for question_id, value in answers_by_question.items()
    ]
    setup_session.setdefault("psychogram", None)
    setup_session.setdefault("policy_preview", None)
    store[setup_session_id] = setup_session
    save_sessions(store)

    return {
        "setup_session_id": setup_session_id,
        "user_id": payload.user_id,
        "character_id": payload.character_id,
        "status": "setup_in_progress",
        "seal_mode": payload.seal_mode,
        "initial_seal_number": payload.initial_seal_number,
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "language": lang,
        "integrations": effective_integrations,
        "integration_config": effective_integration_config,
        "instruction_style": payload.instruction_style,
        "desired_intensity": payload.desired_intensity,
        "grooming_preference": payload.grooming_preference,
        "escalation_mode": setup_session.get("escalation_mode", "moderate"),
        "contract": {
            "start_date": contract_start_date,
            "end_date": contract_end_date,
            "min_end_date": contract_min_end_date,
            "max_end_date": contract_max_end_date,
            "ai_controls_end_date": payload.ai_controls_end_date,
            "max_penalty_per_day_minutes": payload.max_penalty_per_day_minutes,
            "max_penalty_per_week_minutes": payload.max_penalty_per_week_minutes,
            "opening_limit_period": opening_limit_period,
            "max_openings_in_period": max_openings_in_period,
            "opening_window_minutes": payload.opening_window_minutes,
        },
        "questions": _localized_questions(lang),
    }

@router.post("/sessions/{setup_session_id}/answers")
def submit_setup_answers(setup_session_id: str, payload: SetupAnswersRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    lang = _lang(setup_session["language"])
    if setup_session["status"] != "setup_in_progress":
        raise HTTPException(status_code=409, detail=_t(lang, "not_editable"))

    known_ids = set(QUESTION_IDS)
    question_map = {q["id"]: q for q in QUESTION_BANK}
    for answer in payload.answers:
        if answer.question_id not in known_ids:
            raise HTTPException(status_code=400, detail=f"{_t(lang, 'unknown_question')}: {answer.question_id}")
        try:
            _validate_answer(question_map[answer.question_id], answer.value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    answers_by_question = {entry["question_id"]: entry["value"] for entry in setup_session["answers"]}
    for answer in payload.answers:
        answers_by_question[answer.question_id] = answer.value
    _validate_safety_answers(answers_by_question)

    setup_session["answers"] = [
        {"question_id": question_id, "value": value}
        for question_id, value in answers_by_question.items()
    ]
    setup_session["psychogram"] = _build_psychogram(setup_session)
    setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])
    setup_session["policy_preview"].setdefault("contract", {})
    setup_session["policy_preview"]["contract"]["proposed_end_date"] = None
    generated_contract = (setup_session["policy_preview"] or {}).get("generated_contract")
    if generated_contract:
        setup_session["policy_preview"].pop("generated_contract", None)
    setup_session["psychogram_analysis"] = None
    setup_session["psychogram_analysis_status"] = "idle"
    setup_session["psychogram_analysis_generated_at"] = None
    setup_session["contract_generation_status"] = "idle"
    setup_session["contract_generated_at"] = None
    setup_session["ai_proposed_end_date"] = None

    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)
    applied_to_active_session = sync_setup_snapshot_to_active_session(request, setup_session)

    return {
        "setup_session_id": setup_session_id,
        "status": setup_session["status"],
        "answered_questions": len(setup_session["answers"]),
        "total_questions": len(QUESTION_IDS),
        "psychogram_preview": setup_session["psychogram"],
        "policy_preview": setup_session["policy_preview"],
        "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
        "applied_to_active_session": applied_to_active_session,
    }

@router.get("/sessions/{setup_session_id}")
def get_setup_session(setup_session_id: str) -> dict:
    return _get_session_or_404(setup_session_id)


@router.post("/sessions/{setup_session_id}/integrations")
def update_setup_integrations(
    setup_session_id: str,
    payload: SetupIntegrationsUpdateRequest,
    request: Request,
) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    normalized_integrations = [str(item).strip().lower() for item in (payload.integrations or []) if str(item).strip()]
    integration_config = payload.integration_config if isinstance(payload.integration_config, dict) else {}
    _validate_ttlock_config(normalized_integrations, integration_config)
    _validate_chaster_config(normalized_integrations, integration_config)

    setup_session["integrations"] = normalized_integrations
    setup_session["integration_config"] = integration_config
    if isinstance(setup_session.get("policy_preview"), dict):
        setup_session["policy_preview"]["integrations"] = normalized_integrations
        setup_session["policy_preview"]["integration_config"] = integration_config
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    applied_to_active_session = sync_setup_snapshot_to_active_session(request, setup_session)
    return {
        "setup_session_id": setup_session_id,
        "status": setup_session.get("status", "setup_in_progress"),
        "integrations": normalized_integrations,
        "integration_config": integration_config,
        "applied_to_active_session": applied_to_active_session,
    }

@router.post("/sessions/{setup_session_id}/seal")
def update_setup_seal(
    setup_session_id: str,
    payload: SetupSealUpdateRequest,
    request: Request,
) -> dict:
    """
    Update seal/plomb mode for a setup session.
    
    Allowed modes:
    - "none": No seal (seal text not required on hygiene_close)
    - "plomben": Tagebuch-style numbered seal (seal text required on hygiene_close)
    - "versiegelung": Full seal mode (seal text required on hygiene_close)
    """
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    seal_mode = str(payload.seal_mode).strip().lower()
    if seal_mode not in {"none", "plomben", "versiegelung"}:
        seal_mode = "none"

    setup_session["seal_mode"] = seal_mode
    if isinstance(setup_session.get("policy_preview"), dict):
        setup_session["policy_preview"]["seal"] = {
            "mode": seal_mode,
            "required_on_close": seal_mode in {"plomben", "versiegelung"},
        }
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    applied_to_active_session = sync_setup_snapshot_to_active_session(request, setup_session)
    return {
        "setup_session_id": setup_session_id,
        "status": setup_session.get("status", "setup_in_progress"),
        "seal_mode": seal_mode,
        "applied_to_active_session": applied_to_active_session,
    }

@router.post("/sessions/{setup_session_id}/complete")
def complete_setup_session(setup_session_id: str, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    lang = _lang(setup_session["language"])
    if setup_session["status"] != "setup_in_progress":
        raise HTTPException(status_code=409, detail=_t(lang, "cannot_complete"))
    if len(setup_session["answers"]) < 6:
        raise HTTPException(status_code=400, detail=_t(lang, "not_enough_answers"))
    _validate_safety_answers({entry["question_id"]: entry["value"] for entry in setup_session["answers"]})

    if setup_session["psychogram"] is None:
        setup_session["psychogram"] = _build_psychogram(setup_session)
    if setup_session["policy_preview"] is None:
        setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])

    setup_session["psychogram_analysis_status"] = "generating"
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    db = get_db_session(request)
    try:
        analysis_text, proposed_end_date = generate_psychogram_analysis_with_end_date_for_setup(db, request, setup_session)
        generated_at = _now_iso()
        setup_session["psychogram_analysis"] = analysis_text
        setup_session["psychogram_analysis_status"] = "ready"
        setup_session["psychogram_analysis_generated_at"] = generated_at
        setup_session["ai_proposed_end_date"] = proposed_end_date
        setup_session["psychogram"]["analysis"] = analysis_text
        setup_session["updated_at"] = generated_at
    except Exception:
        setup_session["psychogram_analysis_status"] = "error"
        setup_session["updated_at"] = _now_iso()
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        db.close()
        raise

    setup_session["policy_preview"].setdefault("contract", {})
    setup_session["policy_preview"]["contract"]["proposed_end_date"] = setup_session.get("ai_proposed_end_date")
    setup_session["policy_preview"]["generated_contract"] = {
        "status": "pending",
        "text": None,
        "generated_at": None,
        "consent": {
            "required_text": _required_contract_consent_text(lang),
            "accepted": False,
            "consent_text": None,
            "accepted_at": None,
        },
        "technical_info": {"consent": None},
    }
    setup_session["psychogram_analysis"] = analysis_text
    setup_session["psychogram_analysis_status"] = "ready"
    setup_session["psychogram_analysis_generated_at"] = generated_at
    setup_session["contract_generation_status"] = "pending"
    setup_session["contract_generated_at"] = None
    setup_session["ai_proposed_end_date"] = proposed_end_date
    if isinstance(setup_session.get("psychogram"), dict):
        setup_session["psychogram"]["analysis"] = analysis_text

    setup_session["status"] = "configured"
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    # Ensure an active ChastitySession is created from this setup immediately
    try:
        active_session_id = _ensure_active_session_from_setup(db, setup_session)
        db.commit()
    finally:
        db.close()

    store = load_sessions()
    store[setup_session_id] = setup_session
    save_sessions(store)

    return {
        "setup_session_id": setup_session_id,
        "status": "configured",
        "artifacts_status": "pending",
        "artifacts_error": None,
        "psychogram_analysis": setup_session.get("psychogram_analysis"),
        "psychogram_analysis_status": setup_session.get("psychogram_analysis_status"),
        "chastity_session": {
            "session_id": active_session_id,
            "user_id": setup_session["user_id"],
            "character_id": setup_session.get("character_id"),
            "status": "active",
            "policy": setup_session["policy_preview"],
            "psychogram": setup_session["psychogram"],
            "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
            "psychogram_analysis": setup_session.get("psychogram_analysis"),
            "contract_generation_status": setup_session.get("contract_generation_status", "pending"),
        },
    }

@router.post("/sessions/{setup_session_id}/analysis")
def generate_setup_analysis(setup_session_id: str, payload: SetupArtifactsRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if setup_session.get("status") != "configured":
        raise HTTPException(status_code=409, detail="Setup session must be configured first.")
    active_session_id = setup_session.get("active_session_id")

    existing_analysis = setup_session.get("psychogram_analysis") or (setup_session.get("psychogram") or {}).get("analysis")
    existing_proposed_end = ((setup_session.get("policy_preview") or {}).get("contract") or {}).get("proposed_end_date")
    if existing_analysis and not payload.force:
        return {
            "setup_session_id": setup_session_id,
            "session_id": active_session_id,
            "status": "ready",
            "psychogram_analysis": existing_analysis,
            "proposed_end_date": existing_proposed_end,
            "analysis_generated_at": setup_session.get("psychogram_analysis_generated_at"),
        }

    setup_session["psychogram_analysis_status"] = "generating"
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    db = get_db_session(request)
    try:
        analysis_text, proposed_end_date = generate_psychogram_analysis_with_end_date_for_setup(db, request, setup_session)
        generated_at = _now_iso()

        setup_session["psychogram_analysis"] = analysis_text
        setup_session["psychogram_analysis_status"] = "ready"
        setup_session["psychogram_analysis_generated_at"] = generated_at
        setup_session["ai_proposed_end_date"] = proposed_end_date
        if setup_session.get("psychogram") is None:
            setup_session["psychogram"] = _build_psychogram(setup_session)
        setup_session["psychogram"]["analysis"] = analysis_text
        if setup_session.get("policy_preview") is None:
            setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])
        setup_session["policy_preview"].setdefault("contract", {})
        setup_session["policy_preview"]["contract"]["proposed_end_date"] = proposed_end_date
        setup_session["updated_at"] = generated_at
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)

        active_session_id = setup_session.get("active_session_id")
        if active_session_id:
            db_session = db.get(ChastitySession, active_session_id)
            if db_session is not None:
                sync_setup_snapshot_to_active_session_db(db, setup_session)
                system_turn_exists = db.scalar(
                    select(Turn)
                    .where(Turn.session_id == active_session_id)
                    .where(Turn.player_action == "[SYSTEM] psychogram_analysis")
                    .limit(1)
                )
                if system_turn_exists is None:
                    current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == active_session_id))
                    next_turn_no = (current_turn_no or 0) + 1
                    end_line = proposed_end_date or ("AI-decides" if _lang(setup_session.get("language", "de")) == "en" else "KI-entscheidet")
                    summary_message = _system_note(_lang(setup_session.get("language", "de")), "psychogram_ready", end_date=end_line)
                    db.add(
                        Turn(
                            id=str(uuid4()),
                            session_id=active_session_id,
                            turn_no=next_turn_no,
                            player_action="[SYSTEM] psychogram_analysis",
                            ai_narration=summary_message,
                            language=_lang(setup_session.get("language", "de")),
                            created_at=datetime.now(UTC),
                        )
                    )
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        setup_session["psychogram_analysis_status"] = "error"
        setup_session["updated_at"] = _now_iso()
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        raise HTTPException(status_code=500, detail=f"Psychogram analysis failed: {exc}") from exc
    finally:
        db.close()

    return {
        "setup_session_id": setup_session_id,
        "session_id": active_session_id,
        "status": "ready",
        "psychogram_analysis": setup_session.get("psychogram_analysis"),
        "proposed_end_date": ((setup_session.get("policy_preview") or {}).get("contract") or {}).get("proposed_end_date"),
        "analysis_generated_at": setup_session.get("psychogram_analysis_generated_at"),
    }

@router.post("/sessions/{setup_session_id}/contract")
def generate_setup_contract(setup_session_id: str, payload: SetupArtifactsRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if setup_session.get("status") != "configured":
        raise HTTPException(status_code=409, detail="Setup session must be configured first.")
    if setup_session.get("psychogram_analysis_status") not in {"ready"}:
        raise HTTPException(status_code=409, detail="Psychogram analysis must be generated first.")
    active_session_id = setup_session.get("active_session_id")

    existing_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("text")
    has_unresolved_placeholders = "{{" in str(existing_contract or "") and "}}" in str(existing_contract or "")
    if existing_contract and not payload.force and not has_unresolved_placeholders:
        consent = _ensure_generated_contract_consent(setup_session)
        generated_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {})
        generated_contract.setdefault("technical_info", {})
        generated_contract["technical_info"]["consent"] = _consent_technical_info(setup_session)
        rendered_contract = _render_contract_with_consent(existing_contract, setup_session)
        db = get_db_session(request)
        try:
            active_session_id = _ensure_active_session_from_setup(db, setup_session)
            sync_setup_snapshot_to_active_session_db(db, setup_session)
            db.commit()
        finally:
            db.close()
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        return {
            "setup_session_id": setup_session_id,
            "session_id": active_session_id,
            "status": "ready",
            "contract_text": rendered_contract,
            "contract_generated_at": setup_session.get("contract_generated_at"),
            "consent": consent,
        }

    setup_session["contract_generation_status"] = "generating"
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    db = get_db_session(request)
    try:
        contract_text = generate_contract_for_setup(db, request, setup_session)
        generated_at = _now_iso()
        if setup_session.get("policy_preview") is None:
            setup_session["policy_preview"] = _build_policy(setup_session, setup_session.get("psychogram") or {})
        consent_state = _ensure_generated_contract_consent(setup_session)
        consent_state["required_text"] = _required_contract_consent_text(setup_session.get("language", "de"))
        consent_state["accepted"] = False
        consent_state["consent_text"] = None
        consent_state["accepted_at"] = None
        setup_session["policy_preview"]["generated_contract"] = {
            "status": "ready",
            "text": contract_text,
            "generated_at": generated_at,
            "consent": consent_state,
            "technical_info": {
                "consent": _consent_technical_info(setup_session),
                "template_text": str(setup_session.pop("_contract_template_text", "") or ""),
                "ai_edits": list(setup_session.pop("_contract_ai_edits", []) or []),
                "diff_preview": str(setup_session.pop("_contract_diff_preview", "") or ""),
            },
        }
        setup_session["contract_generation_status"] = "ready"
        setup_session["contract_generated_at"] = generated_at
        setup_session["updated_at"] = generated_at
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        active_session_id = _ensure_active_session_from_setup(db, setup_session)
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        sync_setup_snapshot_to_active_session_db(db, setup_session)

        system_turn_exists = db.scalar(
            select(Turn)
            .where(Turn.session_id == active_session_id)
            .where(Turn.player_action == "[SYSTEM] generated_contract")
            .limit(1)
        )
        if system_turn_exists is None:
            current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == active_session_id))
            next_turn_no = (current_turn_no or 0) + 1
            db.add(
                Turn(
                    id=str(uuid4()),
                    session_id=active_session_id,
                    turn_no=next_turn_no,
                    player_action="[SYSTEM] generated_contract",
                    ai_narration=_system_note(_lang(setup_session.get("language", "de")), "contract_ready"),
                    language=_lang(setup_session.get("language", "de")),
                    created_at=datetime.now(UTC),
                )
            )
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        setup_session["contract_generation_status"] = "error"
        setup_session["updated_at"] = _now_iso()
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        status = 504 if _is_llm_timeout_error(exc) else 500
        raise HTTPException(status_code=status, detail=f"Contract generation failed: {exc}") from exc
    finally:
        db.close()

    return {
        "setup_session_id": setup_session_id,
        "session_id": active_session_id,
        "status": "ready",
        "contract_text": _render_contract_with_consent(
            ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("text"),
            setup_session,
        ),
        "contract_generated_at": setup_session.get("contract_generated_at"),
        "consent": ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("consent"),
    }

@router.post("/sessions/{setup_session_id}/contract/accept")
def accept_setup_contract(setup_session_id: str, payload: SetupContractConsentRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if setup_session.get("status") != "configured":
        raise HTTPException(status_code=409, detail="Setup session must be configured first.")

    generated_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {})
    contract_text = generated_contract.get("text")
    if not contract_text:
        raise HTTPException(status_code=409, detail="Contract must be generated before consent.")

    consent = _ensure_generated_contract_consent(setup_session)
    required_text = str(consent.get("required_text") or _required_contract_consent_text(setup_session.get("language", "de")))
    provided_text = str(payload.consent_text or "").strip()
    if _normalize_consent_for_compare(provided_text) != _normalize_consent_for_compare(required_text):
        raise HTTPException(status_code=400, detail=f"Consent text mismatch. Required: {required_text}")

    _maybe_create_chaster_session_on_contract_accept(
        setup_session=setup_session,
        user_id=payload.user_id,
        auth_token=payload.auth_token,
        request=request,
    )

    accepted_at = _now_iso()
    consent["required_text"] = required_text
    consent["accepted"] = True
    consent["consent_text"] = provided_text
    consent["accepted_at"] = accepted_at
    generated_contract["text"] = _render_contract_with_consent(generated_contract.get("text"), setup_session)
    generated_contract.setdefault("technical_info", {})
    generated_contract["technical_info"]["consent"] = _consent_technical_info(setup_session)
    setup_session["updated_at"] = accepted_at
    store[setup_session_id] = setup_session
    save_sessions(store)

    active_session_id = setup_session.get("active_session_id")
    db = get_db_session(request)
    try:
        if active_session_id:
            db_session = db.get(ChastitySession, active_session_id)
            if db_session is not None:
                sync_setup_snapshot_to_active_session_db(db, setup_session)
                current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == active_session_id))
                next_turn_no = (current_turn_no or 0) + 1
                lang = _lang(setup_session.get("language", "de"))
                ai_msg = _system_note(lang, "consent_done", accepted_at=accepted_at)
                db.add(
                    Turn(
                        id=str(uuid4()),
                        session_id=active_session_id,
                        turn_no=next_turn_no,
                        player_action="[SYSTEM] contract_consent",
                        ai_narration=ai_msg,
                        language=lang,
                        created_at=datetime.now(UTC),
                    )
                )
        db.commit()
    finally:
        db.close()

    return {
        "setup_session_id": setup_session_id,
        "session_id": active_session_id,
        "status": "accepted",
        "consent": consent,
        "contract_text": generated_contract.get("text"),
    }

@router.post("/sessions/{setup_session_id}/artifacts")
def generate_setup_artifacts(setup_session_id: str, payload: SetupArtifactsRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if setup_session.get("status") != "configured":
        raise HTTPException(status_code=409, detail="Setup session must be configured first.")
    active_session_id = setup_session.get("active_session_id")

    existing_analysis = setup_session.get("psychogram_analysis") or (setup_session.get("psychogram") or {}).get("analysis")
    existing_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("text")
    has_unresolved_placeholders = "{{" in str(existing_contract or "") and "}}" in str(existing_contract or "")
    if existing_analysis and existing_contract and not payload.force and not has_unresolved_placeholders:
        consent = _ensure_generated_contract_consent(setup_session)
        generated_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {})
        generated_contract.setdefault("technical_info", {})
        generated_contract["technical_info"]["consent"] = _consent_technical_info(setup_session)
        rendered_contract = _render_contract_with_consent(existing_contract, setup_session)
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        db = get_db_session(request)
        try:
            active_session_id = _ensure_active_session_from_setup(db, setup_session)
            sync_setup_snapshot_to_active_session_db(db, setup_session)
            db.commit()
        finally:
            db.close()
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        return {
            "setup_session_id": setup_session_id,
            "session_id": active_session_id,
            "status": "ready",
            "psychogram_analysis": existing_analysis,
            "contract_text": rendered_contract,
            "contract_generated_at": setup_session.get("contract_generated_at"),
            "consent": consent,
        }

    setup_session["contract_generation_status"] = "generating"
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    db = get_db_session(request)
    try:
        analysis, proposed_end_date = generate_psychogram_analysis_with_end_date_for_setup(db, request, setup_session)
        contract_text = generate_contract_for_setup(db, request, setup_session)
        generated_at = _now_iso()

        setup_session["psychogram_analysis"] = analysis
        setup_session["psychogram_analysis_status"] = "ready"
        setup_session["psychogram_analysis_generated_at"] = generated_at
        setup_session["ai_proposed_end_date"] = proposed_end_date
        if setup_session.get("psychogram") is None:
            setup_session["psychogram"] = _build_psychogram(setup_session)
        setup_session["psychogram"]["analysis"] = analysis
        if setup_session.get("policy_preview") is None:
            setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])
        setup_session["policy_preview"].setdefault("contract", {})
        setup_session["policy_preview"]["contract"]["proposed_end_date"] = proposed_end_date
        consent_state = _ensure_generated_contract_consent(setup_session)
        consent_state["required_text"] = _required_contract_consent_text(setup_session.get("language", "de"))
        consent_state["accepted"] = False
        consent_state["consent_text"] = None
        consent_state["accepted_at"] = None
        setup_session["policy_preview"]["generated_contract"] = {
            "status": "ready",
            "text": contract_text,
            "generated_at": generated_at,
            "consent": consent_state,
            "technical_info": {
                "consent": _consent_technical_info(setup_session),
                "template_text": str(setup_session.pop("_contract_template_text", "") or ""),
                "ai_edits": list(setup_session.pop("_contract_ai_edits", []) or []),
                "diff_preview": str(setup_session.pop("_contract_diff_preview", "") or ""),
            },
        }
        setup_session["contract_generation_status"] = "ready"
        setup_session["contract_generated_at"] = generated_at
        setup_session["updated_at"] = generated_at
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        active_session_id = _ensure_active_session_from_setup(db, setup_session)
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        sync_setup_snapshot_to_active_session_db(db, setup_session)

        system_turn_exists = db.scalar(
            select(Turn)
            .where(Turn.session_id == active_session_id)
            .where(Turn.player_action == "[SYSTEM] setup_analysis_contract")
            .limit(1)
        )
        if system_turn_exists is None:
            current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == active_session_id))
            next_turn_no = (current_turn_no or 0) + 1
            end_line = proposed_end_date or ("AI-decides" if _lang(setup_session.get("language", "de")) == "en" else "KI-entscheidet")
            contract_message = _system_note(
                _lang(setup_session.get("language", "de")),
                "artifacts_ready",
                end_date=end_line,
            )
            db.add(
                Turn(
                    id=str(uuid4()),
                    session_id=active_session_id,
                    turn_no=next_turn_no,
                    player_action="[SYSTEM] setup_analysis_contract",
                    ai_narration=contract_message,
                    language=_lang(setup_session.get("language", "de")),
                    created_at=datetime.now(UTC),
                )
            )
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        setup_session["contract_generation_status"] = "error"
        setup_session["updated_at"] = _now_iso()
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        status = 504 if _is_llm_timeout_error(exc) else 500
        raise HTTPException(status_code=status, detail=f"Contract generation failed: {exc}") from exc
    finally:
        db.close()

    return {
        "setup_session_id": setup_session_id,
        "session_id": active_session_id,
        "status": "ready",
        "psychogram_analysis": setup_session.get("psychogram_analysis"),
        "contract_text": _render_contract_with_consent(
            ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("text"),
            setup_session,
        ),
        "contract_generated_at": setup_session.get("contract_generated_at"),
        "consent": ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("consent"),
    }

@router.patch("/sessions/{setup_session_id}/psychogram")
def recalibrate_psychogram(setup_session_id: str, payload: PsychogramRecalibrationRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    lang = _lang(setup_session["language"])

    if setup_session["psychogram"] is None:
        setup_session["psychogram"] = _build_psychogram(setup_session)

    for key, value in payload.trait_overrides.items():
        if key in TRAIT_KEYS:
            setup_session["psychogram"]["traits"][key] = max(0, min(100, value))

    setup_session["psychogram"]["updated_at"] = _now_iso()
    setup_session["psychogram"]["update_reason"] = payload.update_reason
    setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)
    applied_to_active_session = sync_setup_snapshot_to_active_session(request, setup_session)

    return {
        "setup_session_id": setup_session_id,
        "message": _t(lang, "recalibration_done"),
        "psychogram": setup_session["psychogram"],
        "policy_preview": setup_session["policy_preview"],
        "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
        "applied_to_active_session": applied_to_active_session,
    }

@router.post("/sessions/{setup_session_id}/ai-update-fields")
def ai_update_controlled_fields(setup_session_id: str, payload: SetupAIControlledFieldsUpdateRequest, request: Request) -> dict:
    """KI-Endpoint: Aktualisiere während einer aktiven Sitzung die KI-gesteuerten Felder.
    
    Diese Felder werden beim Setup vom Benutzer initialisiert, können aber während
    der aktiven Sitzung NUR von der KI dynamisch angepasst werden:
    
    POLICY-FELDER (Sessionverhalten):
    - contract_min_end_date
    - opening_limit_period, max_openings_in_period, opening_window_minutes
    - seal_mode, initial_seal_number
    
    PSYCHOGRAMM-TRAITS (Präferenzen/Persönlichkeit):
    - structure_need, strictness_affinity, challenge_affinity, praise_affinity
    - accountability_need, novelty_affinity, service_orientation, protocol_affinity
    
    Für den Benutzer sind diese Felder in der aktiven Session read-only.
    """
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session.get("user_id") != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = resolve_user_id_from_token(payload.auth_token, request)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    autonomy_mode = str(setup_session.get("autonomy_mode") or "execute").strip().lower()
    if autonomy_mode != "execute":
        raise HTTPException(
            status_code=409,
            detail="AI field updates are blocked while autonomy_mode='suggest'. Switch to 'execute' to auto-apply.",
        )

    allowed_fields = get_ai_controlled_session_fields()
    policy_fields = get_ai_controlled_policy_fields()
    psychogram_traits = get_ai_controlled_psychogram_traits()

    for field_name in payload.updates.keys():
        if field_name not in allowed_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Field '{field_name}' is not AI-controllable. Allowed: policy fields or psychogram traits.",
            )

    if setup_session.get("psychogram") is None:
        setup_session["psychogram"] = _build_psychogram(setup_session)
    psychogram = setup_session["psychogram"]
    if "traits" not in psychogram:
        psychogram["traits"] = {}
    interaction_preferences = psychogram.setdefault("interaction_preferences", {})
    personal_preferences = psychogram.setdefault("personal_preferences", {})

    policy_updates: dict[str, object] = {}
    psychogram_updates: dict[str, int] = {}

    for field_name, value in payload.updates.items():
        if field_name in policy_fields:
            if field_name == "contract_min_end_date":
                try:
                    date.fromisoformat(str(value))
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}")
                policy_updates[field_name] = str(value)
            elif field_name == "opening_limit_period":
                if str(value) not in {"day", "week", "month"}:
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = str(value)
            elif field_name == "max_openings_in_period":
                try:
                    val = int(value)
                    if val < 0 or val > 200:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = val
            elif field_name == "opening_window_minutes":
                try:
                    val = int(value)
                    if val < 1 or val > 240:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = val
            elif field_name == "seal_mode":
                if str(value) not in {"none", "plomben", "versiegelung"}:
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = str(value)
            elif field_name == "initial_seal_number":
                if value is not None:
                    val_str = str(value).strip()
                    if len(val_str) < 3 and val_str != "":
                        raise HTTPException(status_code=400, detail=f"{field_name} must be at least 3 characters")
                    policy_updates[field_name] = val_str if val_str else None
                else:
                    policy_updates[field_name] = None
            elif field_name == "max_intensity_level":
                try:
                    val = int(value)
                    if val < 1 or val > 5:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}. Must be integer 1-5")
                policy_updates[field_name] = val
            elif field_name == "instruction_style":
                if str(value) not in {"direct_command", "polite_authoritative", "suggestive", "mixed"}:
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = str(value)
            elif field_name == "desired_intensity":
                if str(value) not in {"low", "medium", "strong", "demanding"}:
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = str(value)
            elif field_name == "grooming_preference":
                if str(value) not in {"no_preference", "clean_shaven", "trimmed", "natural"}:
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = str(value)
            elif field_name == "escalation_mode":
                if str(value) not in {"very_slow", "slow", "moderate", "strong", "aggressive"}:
                    raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")
                policy_updates[field_name] = str(value)
        elif field_name in psychogram_traits:
            try:
                val = int(value)
                if val < 0 or val > 100:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Psychogram trait '{field_name}' must be an integer between 0 and 100",
                )
            psychogram_updates[field_name] = val

    changed_fields: list[dict] = []
    for field_name, new_value in policy_updates.items():
        old_value = setup_session.get(field_name)
        if old_value != new_value:
            changed_fields.append({"field": field_name, "old_value": old_value, "new_value": new_value})
        setup_session[field_name] = new_value

    for trait_name, new_value in psychogram_updates.items():
        old_value = psychogram["traits"].get(trait_name)
        if old_value != new_value:
            changed_fields.append({"field": trait_name, "old_value": old_value, "new_value": new_value})
        psychogram["traits"][trait_name] = new_value

    if "instruction_style" in policy_updates:
        interaction_preferences["instruction_style"] = policy_updates["instruction_style"]
    if "desired_intensity" in policy_updates:
        interaction_preferences["desired_intensity"] = policy_updates["desired_intensity"]
    if "escalation_mode" in policy_updates:
        interaction_preferences["escalation_mode"] = policy_updates["escalation_mode"]
    if "grooming_preference" in policy_updates:
        personal_preferences["grooming_preference"] = policy_updates["grooming_preference"]

    if setup_session.get("policy_preview") is None:
        setup_session["policy_preview"] = _build_policy(setup_session, psychogram)

    if psychogram_updates:
        previous_policy = setup_session.get("policy_preview") if isinstance(setup_session.get("policy_preview"), dict) else {}
        previous_generated_contract = previous_policy.get("generated_contract")
        previous_runtime_seal = previous_policy.get("runtime_seal")
        previous_proposed_end_date = ((previous_policy.get("contract") or {}).get("proposed_end_date"))
        setup_session["policy_preview"] = _build_policy(setup_session, psychogram)
        if previous_generated_contract is not None:
            setup_session["policy_preview"]["generated_contract"] = previous_generated_contract
        if previous_runtime_seal is not None:
            setup_session["policy_preview"]["runtime_seal"] = previous_runtime_seal
        if previous_proposed_end_date is not None:
            setup_session["policy_preview"].setdefault("contract", {})
            setup_session["policy_preview"]["contract"]["proposed_end_date"] = previous_proposed_end_date

    policy_preview = setup_session.setdefault("policy_preview", {})
    limits = policy_preview.setdefault("limits", {})
    contract = policy_preview.setdefault("contract", {})
    seal = policy_preview.setdefault("seal", {})
    interaction_profile = policy_preview.setdefault("interaction_profile", {})

    if "contract_min_end_date" in policy_updates:
        contract["min_end_date"] = policy_updates["contract_min_end_date"]
    if "opening_limit_period" in policy_updates:
        limits["opening_limit_period"] = policy_updates["opening_limit_period"]
        if policy_updates["opening_limit_period"] == "day":
            limits["max_openings_per_day"] = int(policy_updates.get("max_openings_in_period", setup_session.get("max_openings_in_period", 0)))
        else:
            limits["max_openings_per_day"] = 0
    if "max_openings_in_period" in policy_updates:
        limits["max_openings_in_period"] = policy_updates["max_openings_in_period"]
        if str(setup_session.get("opening_limit_period") or "day") == "day":
            limits["max_openings_per_day"] = policy_updates["max_openings_in_period"]
    if "opening_window_minutes" in policy_updates:
        limits["opening_window_minutes"] = policy_updates["opening_window_minutes"]
    if "max_intensity_level" in policy_updates:
        limits["max_intensity_level"] = policy_updates["max_intensity_level"]
    if "seal_mode" in policy_updates:
        seal["mode"] = policy_updates["seal_mode"]
        seal["required_on_close"] = policy_updates["seal_mode"] in {"plomben", "versiegelung"}
    if "initial_seal_number" in policy_updates:
        seal["initial_number"] = policy_updates["initial_seal_number"]
    if "instruction_style" in policy_updates:
        interaction_profile["instruction_style"] = policy_updates["instruction_style"]
    if "escalation_mode" in policy_updates:
        interaction_profile["escalation_mode"] = policy_updates["escalation_mode"]

    if "desired_intensity" in policy_updates:
        answers_by_question = {
            str(entry.get("question_id")): entry.get("value")
            for entry in (setup_session.get("answers") or [])
            if isinstance(entry, dict) and str(entry.get("question_id") or "").strip()
        }
        answers_by_question["q6_intensity_1_5"] = _desired_intensity_to_scale_100(str(policy_updates["desired_intensity"]))
        setup_session["answers"] = [
            {"question_id": question_id, "value": value}
            for question_id, value in answers_by_question.items()
        ]
    if "instruction_style" in policy_updates:
        answers_by_question = {
            str(entry.get("question_id")): entry.get("value")
            for entry in (setup_session.get("answers") or [])
            if isinstance(entry, dict) and str(entry.get("question_id") or "").strip()
        }
        answers_by_question["q8_instruction_style"] = policy_updates["instruction_style"]
        setup_session["answers"] = [
            {"question_id": question_id, "value": value}
            for question_id, value in answers_by_question.items()
        ]
    if "grooming_preference" in policy_updates:
        answers_by_question = {
            str(entry.get("question_id")): entry.get("value")
            for entry in (setup_session.get("answers") or [])
            if isinstance(entry, dict) and str(entry.get("question_id") or "").strip()
        }
        answers_by_question["q12_grooming_preference"] = policy_updates["grooming_preference"]
        setup_session["answers"] = [
            {"question_id": question_id, "value": value}
            for question_id, value in answers_by_question.items()
        ]

    update_ts = _now_iso()
    setup_session["psychogram"]["updated_at"] = update_ts
    if payload.reason:
        setup_session["psychogram"]["ai_update_reason"] = payload.reason
        setup_session["ai_update_reason"] = payload.reason
        setup_session["ai_update_timestamp"] = update_ts
    setup_session["updated_at"] = update_ts

    store[setup_session_id] = setup_session
    save_sessions(store)
    applied_to_active_session = sync_setup_snapshot_to_active_session(request, setup_session)

    active_session_id = str(setup_session.get("active_session_id") or "").strip()
    audit_logged_count = 0
    if active_session_id and changed_fields:
        db = get_db_session(request)
        try:
            for change in changed_fields:
                record_audit_event(
                    db=db,
                    session_id=active_session_id,
                    user_id=setup_session["user_id"],
                    event_type="ai_controlled_field_updated",
                    detail=f"AI adjusted '{change['field']}' during session.",
                    metadata={
                        "field": change["field"],
                        "old_value": change["old_value"],
                        "new_value": change["new_value"],
                        "reason": payload.reason or None,
                        "autonomy_mode": autonomy_mode,
                        "source": "setup_ai_update_fields",
                    },
                )
                audit_logged_count += 1
            db.commit()
        finally:
            db.close()

    return {
        "setup_session_id": setup_session_id,
        "message": "AI-controlled fields updated successfully",
        "updated_fields": list(payload.updates.keys()),
        "changed_fields": changed_fields,
        "policy_updates": policy_updates,
        "psychogram_updates": psychogram_updates,
        "audit_logged_count": audit_logged_count,
        "applied_to_active_session": applied_to_active_session,
        "setup_session": {
            "psychogram": setup_session.get("psychogram"),
            "policy_preview": setup_session.get("policy_preview"),
        },
    }

@router.get("/questionnaire")
def get_setup_questionnaire(language: Literal["de", "en"] = "de") -> dict:
    lang = _lang(language)
    return {
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "language": lang,
        "questions": _localized_questions(lang),
    }

@router.get("/demo")
def setup_demo_redirect():
    return RedirectResponse(url="/app", status_code=307)
