import json
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from chastease.api.questionnaire import QUESTION_BANK, QUESTION_IDS, QUESTIONNAIRE_VERSION, TRAIT_KEYS
from chastease.api.schemas import (
    PsychogramRecalibrationRequest,
    SetupAnswersRequest,
    SetupArtifactsRequest,
    SetupChatPreviewRequest,
    SetupContractConsentRequest,
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

router = APIRouter(prefix="/setup", tags=["setup"])


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
    finally:
        db.close()

    store = load_sessions()
    setup_session_id, setup_session = _find_user_setup_session(store, payload.user_id, {"draft", "setup_in_progress"})
    if setup_session is None:
        setup_session = _create_draft_setup_session(payload.user_id, lang)
        setup_session_id = setup_session["setup_session_id"]

    setup_session.update(
        {
            "setup_session_id": setup_session_id,
            "user_id": payload.user_id,
            "character_id": payload.character_id,
            "status": "setup_in_progress",
            "hard_stop_enabled": payload.hard_stop_enabled,
            "autonomy_mode": payload.autonomy_mode,
            "integrations": payload.integrations,
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
            "questionnaire_version": QUESTIONNAIRE_VERSION,
            "updated_at": now,
            "psychogram_analysis": None,
            "psychogram_analysis_status": "idle",
            "psychogram_analysis_generated_at": None,
            "contract_generation_status": "idle",
            "contract_generated_at": None,
            "ai_proposed_end_date": None,
        }
    )
    if "created_at" not in setup_session:
        setup_session["created_at"] = now
    # keep previous answers to allow iterative setup editing without data loss
    setup_session.setdefault("answers", [])
    setup_session.setdefault("psychogram", None)
    setup_session.setdefault("policy_preview", None)
    save_sessions(store)

    return {
        "setup_session_id": setup_session_id,
        "user_id": payload.user_id,
        "character_id": payload.character_id,
        "status": "setup_in_progress",
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "language": lang,
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
    setup_session["policy_preview"].setdefault("contract", {})
    setup_session["policy_preview"]["contract"]["proposed_end_date"] = None
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
    setup_session["psychogram_analysis"] = None
    setup_session["psychogram_analysis_status"] = "pending"
    setup_session["psychogram_analysis_generated_at"] = None
    setup_session["contract_generation_status"] = "pending"
    setup_session["contract_generated_at"] = None
    setup_session["ai_proposed_end_date"] = None
    if isinstance(setup_session.get("psychogram"), dict):
        setup_session["psychogram"].pop("analysis", None)

    setup_session["status"] = "configured"
    setup_session["updated_at"] = _now_iso()
    session_id = str(uuid4())
    setup_session["active_session_id"] = session_id
    store[setup_session_id] = setup_session
    save_sessions(store)

    db = get_db_session(request)
    try:
        db_session = ChastitySession(
            id=session_id,
            user_id=setup_session["user_id"],
            character_id=setup_session.get("character_id"),
            status="active",
            language=setup_session["language"],
            policy_snapshot_json=json.dumps(setup_session["policy_preview"]),
            psychogram_snapshot_json=json.dumps(setup_session["psychogram"]),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(db_session)
        db.commit()
    finally:
        db.close()
    store[setup_session_id] = setup_session
    save_sessions(store)

    return {
        "setup_session_id": setup_session_id,
        "status": "configured",
        "chastity_session": {
            "session_id": session_id,
            "user_id": setup_session["user_id"],
            "character_id": setup_session.get("character_id"),
            "status": "active",
            "policy": setup_session["policy_preview"],
            "psychogram": setup_session["psychogram"],
            "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
            "psychogram_analysis": None,
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
    if not active_session_id:
        raise HTTPException(status_code=409, detail="No active session linked to setup session.")

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

        db_session = db.get(ChastitySession, active_session_id)
        if db_session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
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
    if not active_session_id:
        raise HTTPException(status_code=409, detail="No active session linked to setup session.")

    existing_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("text")
    if existing_contract and not payload.force:
        consent = _ensure_generated_contract_consent(setup_session)
        generated_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {})
        generated_contract.setdefault("technical_info", {})
        generated_contract["technical_info"]["consent"] = _consent_technical_info(setup_session)
        rendered_contract = _render_contract_with_consent(existing_contract, setup_session)
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        sync_setup_snapshot_to_active_session(request, setup_session)
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
            "technical_info": {"consent": _consent_technical_info(setup_session)},
        }
        setup_session["contract_generation_status"] = "ready"
        setup_session["contract_generated_at"] = generated_at
        setup_session["updated_at"] = generated_at
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)

        db_session = db.get(ChastitySession, active_session_id)
        if db_session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
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
        raise HTTPException(status_code=500, detail=f"Contract generation failed: {exc}") from exc
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
    if not active_session_id:
        raise HTTPException(status_code=409, detail="No active session linked to setup session.")

    existing_analysis = setup_session.get("psychogram_analysis") or (setup_session.get("psychogram") or {}).get("analysis")
    existing_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {}).get("text")
    if existing_analysis and existing_contract and not payload.force:
        consent = _ensure_generated_contract_consent(setup_session)
        generated_contract = ((setup_session.get("policy_preview") or {}).get("generated_contract") or {})
        generated_contract.setdefault("technical_info", {})
        generated_contract["technical_info"]["consent"] = _consent_technical_info(setup_session)
        rendered_contract = _render_contract_with_consent(existing_contract, setup_session)
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)
        sync_setup_snapshot_to_active_session(request, setup_session)
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
            "technical_info": {"consent": _consent_technical_info(setup_session)},
        }
        setup_session["contract_generation_status"] = "ready"
        setup_session["contract_generated_at"] = generated_at
        setup_session["updated_at"] = generated_at
        store = load_sessions()
        store[setup_session_id] = setup_session
        save_sessions(store)

        db_session = db.get(ChastitySession, active_session_id)
        if db_session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
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
        raise HTTPException(status_code=500, detail=f"Contract generation failed: {exc}") from exc
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


