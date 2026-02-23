from datetime import UTC, date, datetime, timedelta
import base64
import json
import hashlib
import hmac
from pathlib import Path
import re
import secrets
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from chastease.api.questionnaire import (
    QUESTIONNAIRE_VERSION,
    QUESTION_BANK,
    QUESTION_IDS,
    SUPPORTED_LANGUAGES,
    TRAIT_KEYS,
    TRANSLATIONS,
)
from chastease.models import Character, ChastitySession, LLMProfile, Turn, User
from chastease.repositories.setup_store import load_sessions, save_sessions
from chastease.shared.secrets_crypto import decrypt_secret, encrypt_secret
from chastease.services.ai.base import StoryTurnContext

api_router = APIRouter()
auth_tokens: dict[str, str] = {}
AUTH_TOKEN_VERSION = "v1"



def _lang(value: str) -> str:
    return value if value in SUPPORTED_LANGUAGES else "de"


def _t(lang: str, key: str) -> str:
    return TRANSLATIONS[_lang(lang)][key]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _mint_auth_token(user_id: str, secret_key: str) -> str:
    issued_at = int(datetime.now(UTC).timestamp())
    nonce = secrets.token_hex(8)
    payload = f"{AUTH_TOKEN_VERSION}:{user_id}:{issued_at}:{nonce}"
    signature = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{_b64url_encode(payload.encode('utf-8'))}.{_b64url_encode(signature)}"


def _verify_auth_token(token: str, secret_key: str, ttl_days: int) -> str | None:
    if "." not in token:
        return None
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        provided_sig = _b64url_decode(signature_part)
    except Exception:
        return None

    expected_sig = hmac.new(secret_key.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    try:
        payload = payload_bytes.decode("utf-8")
        version, user_id, issued_at_raw, _nonce = payload.split(":", 3)
    except Exception:
        return None
    if version != AUTH_TOKEN_VERSION:
        return None
    try:
        issued_at = int(issued_at_raw)
    except ValueError:
        return None
    ttl_seconds = max(1, ttl_days) * 24 * 60 * 60
    now_ts = int(datetime.now(UTC).timestamp())
    if issued_at > now_ts + 60:
        return None
    if now_ts - issued_at > ttl_seconds:
        return None
    return user_id


def _resolve_user_id_from_token(auth_token: str, request: Request) -> str | None:
    cached = auth_tokens.get(auth_token)
    if cached:
        return cached
    secret_key = request.app.state.config.SECRET_KEY
    ttl_days = int(getattr(request.app.state.config, "AUTH_TOKEN_TTL_DAYS", 30))
    user_id = _verify_auth_token(auth_token, secret_key, ttl_days)
    if user_id:
        auth_tokens[auth_token] = user_id
    return user_id


def _resolve_contract_dates(
    start_raw: str | None,
    end_raw: str | None,
    min_end_raw: str | None,
    max_end_raw: str | None,
    ai_controls_end_date: bool,
) -> tuple[str, str | None, str | None, str | None]:
    today = datetime.now(UTC).date()
    default_start = today
    default_max_end = today + timedelta(days=30)

    try:
        start_date = date.fromisoformat(start_raw) if start_raw else default_start
        min_end_date = date.fromisoformat(min_end_raw) if min_end_raw else None
        max_end_date = date.fromisoformat(max_end_raw) if max_end_raw else None
        end_date = date.fromisoformat(end_raw) if end_raw else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc

    if max_end_date is None and not ai_controls_end_date:
        max_end_date = default_max_end

    if min_end_date is not None and min_end_date < start_date:
        raise HTTPException(status_code=400, detail="contract_min_end_date must be on or after contract_start_date.")
    if max_end_date is not None and max_end_date < start_date:
        raise HTTPException(status_code=400, detail="contract_max_end_date must be on or after contract_start_date.")
    if min_end_date is not None and max_end_date is not None and min_end_date > max_end_date:
        raise HTTPException(status_code=400, detail="contract_min_end_date must not be after contract_max_end_date.")
    if end_date is not None:
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="contract_end_date must be on or after contract_start_date.")
        if min_end_date is not None and end_date < min_end_date:
            raise HTTPException(status_code=400, detail="contract_end_date must not be before contract_min_end_date.")
        if max_end_date is not None and end_date > max_end_date:
            raise HTTPException(status_code=400, detail="contract_end_date must not be after contract_max_end_date.")
    return (
        start_date.isoformat(),
        (end_date.isoformat() if end_date else None),
        (min_end_date.isoformat() if min_end_date else None),
        (max_end_date.isoformat() if max_end_date else None),
    )


def _normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format.")
    local, domain = email.split("@", 1)
    if not local or "." not in domain:
        raise HTTPException(status_code=400, detail="Invalid email format.")
    return email


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return f"{salt}${digest}"


def _verify_password(password: str, encoded: str) -> bool:
    if "$" not in encoded:
        return False
    salt, expected = encoded.split("$", 1)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return hmac.compare_digest(actual, expected)


def _localized_questions(language: str) -> list[dict]:
    lang = _lang(language)
    localized = []
    for question in QUESTION_BANK:
        item = {
            "question_id": question["id"],
            "text": question["texts"][lang],
            "type": question["type"],
        }
        if question["type"] == "scale_100":
            item["scale_min"] = 1
            item["scale_max"] = 100
            qid = question["id"]
            if qid == "q6_intensity_1_5":
                item["scale_left"] = "sehr sanft" if lang == "de" else "very gentle"
                item["scale_right"] = "sehr fordernd" if lang == "de" else "very demanding"
            elif qid == "q13_experience_level":
                item["scale_left"] = "Anfaenger" if lang == "de" else "beginner"
                item["scale_right"] = "Experte" if lang == "de" else "expert"
            else:
                item["scale_left"] = "trifft nicht zu" if lang == "de" else "does not apply"
                item["scale_right"] = "trifft sehr zu" if lang == "de" else "applies strongly"
        elif question["type"] == "choice":
            item["options"] = [{"value": opt["value"], "label": opt[lang]} for opt in question["options"]]
        if question.get("read_only") is True:
            item["read_only"] = True
        if isinstance(question.get("default_values"), dict):
            item["default_value"] = str(question["default_values"].get(lang, ""))
        localized.append(item)
    return localized


def _validate_answer(question: dict, raw_value: int | str) -> int | str:
    q_type = question["type"]
    if q_type == "scale_100":
        if not isinstance(raw_value, int) or raw_value < 1 or raw_value > 100:
            raise ValueError("Expected integer value in range 1..100")
        return raw_value
    if q_type == "choice":
        if not isinstance(raw_value, str):
            raise ValueError("Expected string value for choice question")
        allowed = {opt["value"] for opt in question["options"]}
        if raw_value not in allowed:
            raise ValueError("Invalid choice value")
        return raw_value
    if q_type == "text":
        if not isinstance(raw_value, str):
            raise ValueError("Expected string value for text question")
        return raw_value.strip()
    raise ValueError("Unsupported question type")


def _normalize_to_0_100(question_type: str, value: int) -> int:
    if question_type == "scale_100":
        return round(((value - 1) / 99) * 100)
    return 50


def _psychogram_brief(psychogram: dict, policy: dict) -> str:
    traits = psychogram["traits"]
    top_traits = sorted(traits.items(), key=lambda item: item[1], reverse=True)[:3]
    top_text = ", ".join([f"{name}:{score}" for name, score in top_traits])
    tone = policy["interaction_profile"]["preferred_tone"]
    intensity = policy["limits"]["max_intensity_level"]
    return f"Top traits -> {top_text}. Tone={tone}, intensity={intensity}, confidence={psychogram['confidence']}."


def _derive_experience_profile(level: int) -> str:
    if level <= 4:
        return "beginner"
    if level <= 7:
        return "intermediate"
    return "expert"


def _fixed_soft_limits_text(language: str) -> str:
    return (
        "Dynamic during the session via safe communication."
        if _lang(language) == "en"
        else "Dynamisch waehrend der Sitzung durch sichere Kommunikation."
    )


def _required_contract_consent_text(language: str) -> str:
    return "I accept this contract" if _lang(language) == "en" else "Ich akzeptiere diesen Vertrag"


def _normalize_consent_for_compare(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _ensure_generated_contract_consent(setup_session: dict) -> dict:
    lang = _lang(setup_session.get("language", "de"))
    policy = setup_session.setdefault("policy_preview", {})
    generated_contract = policy.setdefault("generated_contract", {})
    consent = generated_contract.setdefault("consent", {})
    consent.setdefault("required_text", _required_contract_consent_text(lang))
    consent.setdefault("accepted", False)
    consent.setdefault("consent_text", None)
    consent.setdefault("accepted_at", None)
    return consent


def _render_contract_with_consent(contract_text: str | None, setup_session: dict) -> str | None:
    if contract_text is None:
        return None
    rendered = str(contract_text)
    fields = _build_contract_template_fields(setup_session)

    signature_date_sub = str(fields.get("signature_date_sub") or "-")
    signature_sub = str(fields.get("signature_sub") or "-")

    rendered = re.sub(
        r"(^\s*-\s*(?:Datum|Date):\s*\*\*\*)[^*\n]*(\*\*\*\s*$)",
        lambda m: f"{m.group(1)}{signature_date_sub}{m.group(2)}",
        rendered,
        count=1,
        flags=re.MULTILINE,
    )
    rendered = re.sub(
        r"(^\s*-\s*(?:Unterschrift\s*Sub|Sub signature):\s*\*\*\*)[^*\n]*(\*\*\*\s*$)",
        lambda m: f"{m.group(1)}{signature_sub}{m.group(2)}",
        rendered,
        count=1,
        flags=re.MULTILINE,
    )

    footer_updates = {
        "consent_accepted": str(fields.get("consent_accepted") or "false"),
        "consent_text": str(fields.get("consent_text") or "-"),
        "consent_accepted_at": str(fields.get("consent_accepted_at") or "-"),
    }
    for key, value in footer_updates.items():
        escaped = json.dumps(value, ensure_ascii=False)[1:-1]
        rendered = re.sub(
            rf'("{re.escape(key)}"\s*:\s*")[^"]*(")',
            lambda m: f'{m.group(1)}{escaped}{m.group(2)}',
            rendered,
            count=1,
        )

    return rendered


def _validate_safety_answers(answers: dict[str, int | str]) -> None:
    # Backward compatible: only enforce required safety payload when mode is explicitly answered.
    mode_raw = answers.get("q10_safety_mode")
    if mode_raw is None:
        return
    mode = str(mode_raw).strip()
    if mode not in {"safeword", "traffic_light"}:
        raise HTTPException(status_code=400, detail="Invalid safety_mode value.")
    if mode == "safeword":
        safeword = str(answers.get("q10_safeword", "")).strip()
        if not safeword:
            raise HTTPException(
                status_code=400, detail="q10_safeword is required when q10_safety_mode is safeword."
            )
        return
    # traffic_light mode uses predefined words/guidance and requires no extra input fields
    return


def _build_psychogram(setup_session: dict) -> dict:
    lang = _lang(setup_session["language"])
    answers = {entry["question_id"]: entry["value"] for entry in setup_session["answers"]}
    question_map = {q["id"]: q for q in QUESTION_BANK}
    weighted_sum = {key: 0.0 for key in TRAIT_KEYS}
    total_weight = {key: 0.0 for key in TRAIT_KEYS}

    for question in QUESTION_BANK:
        answer_value = answers.get(question["id"])
        if answer_value is None or not isinstance(answer_value, int):
            continue
        normalized_answer = _normalize_to_0_100(question["type"], answer_value)
        for trait, weight in question["weights"].items():
            weighted_sum[trait] += normalized_answer * weight
            total_weight[trait] += weight

    traits = {}
    for trait in TRAIT_KEYS:
        if total_weight[trait] == 0:
            traits[trait] = 50
        else:
            traits[trait] = round(weighted_sum[trait] / total_weight[trait])

    dislikes = [trait for trait, score in traits.items() if score <= 35]
    likes = [trait for trait, score in traits.items() if score >= 65]
    scored_count = sum(
        1
        for qid, value in answers.items()
        if qid in question_map and question_map[qid]["type"] == "scale_100" and isinstance(value, int)
    )
    confidence = round(0.2 + (scored_count / 6) * 0.8, 2)
    summary = _t(lang, "summary_template").format(
        structure=traits["structure_need"],
        strictness=traits["strictness_affinity"],
        accountability=traits["accountability_need"],
    )
    autonomy_profile, autonomy_bias = _derive_autonomy_preferences(setup_session, traits)
    praise_timing = _derive_praise_timing(traits)
    instruction_style = answers.get("q8_instruction_style", "mixed")
    escalation_mode = answers.get("q11_escalation_mode", "moderate")
    grooming_preference = answers.get("q12_grooming_preference", "no_preference")
    experience_level_raw = int(answers.get("q13_experience_level", 50))
    experience_level = max(1, min(10, round(experience_level_raw / 10)))
    hard_limits_text = str(answers.get("q14_hard_limits_text", "")).strip()
    taboo_text = answers.get("q7_taboo_text", "")
    open_context = answers.get("q9_open_context", "")
    soft_limits_text = _fixed_soft_limits_text(lang)
    if not hard_limits_text:
        hard_limits_text = str(taboo_text or "").strip()
    safety_mode = str(answers.get("q10_safety_mode", "safeword"))
    safety_profile: dict[str, object] = {"mode": safety_mode}
    if safety_mode == "safeword":
        safeword = str(answers.get("q10_safeword", "")).strip()
        if safeword:
            safety_profile["safeword"] = safeword
        safety_profile["safeword_abort_protocol"] = {
            "mode": "immediate_abort",
            "confirmation_questions_required": 2,
            "reason_required": True,
        }
    elif safety_mode == "traffic_light":
        safety_profile["traffic_light_words"] = {"green": "green", "yellow": "yellow", "red": "red"}
        safety_profile["red_abort_protocol"] = {
            "mode": "immediate_abort",
            "confirmation_questions_required": 2,
            "reason_required": True,
        }

    return {
        "psychogram_version": "2.6.1",
        "source_questionnaire_version": QUESTIONNAIRE_VERSION,
        "source_model": "bdsmtest-inspired",
        "created_at": _now_iso(),
        "updated_at": None,
        "update_reason": "initial_setup",
        "traits": traits,
        "likes": likes,
        "dislikes": dislikes,
        "interaction_preferences": {
            "autonomy_profile": autonomy_profile,
            "autonomy_bias": autonomy_bias,
            "praise_timing": praise_timing,
            "instruction_style": instruction_style,
            "escalation_mode": escalation_mode,
            "experience_level": experience_level,
            "experience_profile": _derive_experience_profile(experience_level),
        },
        "safety_profile": safety_profile,
        "personal_preferences": {
            "grooming_preference": grooming_preference,
        },
        "hard_limits_text": hard_limits_text,
        "soft_limits_text": soft_limits_text,
        "taboo_text": taboo_text,
        "open_context": open_context,
        "summary": summary,
        "confidence": confidence,
    }


def _derive_autonomy_preferences(setup_session: dict, traits: dict) -> tuple[str, int]:
    mode = setup_session["autonomy_mode"]
    accountability = traits["accountability_need"]
    if mode == "suggest":
        return ("suggest_first", min(95, 65 + round(accountability / 10)))
    if accountability >= 80:
        return ("execute_preferred", max(10, 40 - round((accountability - 80) / 2)))
    return ("mixed", 45)


def _derive_praise_timing(traits: dict) -> str:
    praise = traits["praise_affinity"]
    if praise >= 70:
        return "immediate"
    if praise >= 50:
        return "situational"
    if praise >= 35:
        return "delayed"
    return "rare_but_impactful"


def _derive_allowed_categories(traits: dict) -> list[str]:
    categories = ["hygiene", "service", "posture"]
    if traits["challenge_affinity"] >= 60:
        categories.append("edge")
    if traits["novelty_affinity"] >= 60:
        categories.append("challenge_variation")
    if traits["strictness_affinity"] >= 65:
        categories.append("humiliation_light")
    return categories


def _conservative_policy_defaults(setup_session: dict) -> dict:
    day_cap = setup_session.get("max_penalty_per_day_minutes", 60)
    week_cap = setup_session.get("max_penalty_per_week_minutes", 240)
    return {
        "applied": True,
        "reason": "low_confidence",
        "tone": "balanced",
        "max_intensity_level": 2,
        "autonomy_profile": "suggest_first",
        "autonomy_bias": 80,
        "max_penalty_per_day_minutes": 0 if day_cap == 0 else min(day_cap, 20),
        "max_penalty_per_week_minutes": 0 if week_cap == 0 else min(week_cap, 90),
        "hard_stop_enabled": setup_session["hard_stop_enabled"],
    }


def _build_policy(setup_session: dict, psychogram: dict) -> dict:
    traits = psychogram["traits"]
    autonomy_profile = psychogram["interaction_preferences"]["autonomy_profile"]
    autonomy_bias = psychogram["interaction_preferences"]["autonomy_bias"]
    low_confidence = psychogram["confidence"] < 0.5
    conservative = _conservative_policy_defaults(setup_session) if low_confidence else {"applied": False}
    default_limits = conservative if low_confidence else {}

    max_penalty_day = setup_session.get("max_penalty_per_day_minutes", 60)
    max_penalty_week = setup_session.get("max_penalty_per_week_minutes", 240)
    opening_period = setup_session.get("opening_limit_period", "day")
    max_openings = setup_session.get("max_openings_in_period", setup_session.get("max_openings_per_day", 1))
    return {
        "policy_version": "1.1.0",
        "hard_stop_enabled": setup_session["hard_stop_enabled"],
        "autonomy_mode": setup_session["autonomy_mode"],
        "integrations": setup_session["integrations"],
        "limits": {
            "max_intensity_level": default_limits.get(
                "max_intensity_level", max(1, min(5, round(traits["strictness_affinity"] / 20)))
            ),
            "max_penalty_per_day_minutes": default_limits.get(
                "max_penalty_per_day_minutes", max_penalty_day
            ),
            "max_penalty_per_week_minutes": default_limits.get(
                "max_penalty_per_week_minutes", max_penalty_week
            ),
            "allowed_challenge_categories": _derive_allowed_categories(traits),
            "max_openings_per_day": max_openings if opening_period == "day" else 0,
            "opening_limit_period": opening_period,
            "max_openings_in_period": max_openings,
            "opening_window_minutes": setup_session.get("opening_window_minutes", 30),
        },
        "contract": {
            "start_date": setup_session.get("contract_start_date"),
            "end_date": setup_session.get("contract_end_date"),
            "min_end_date": setup_session.get("contract_min_end_date"),
            "max_end_date": setup_session.get("contract_max_end_date", setup_session.get("contract_end_date")),
            "ai_controls_end_date": setup_session.get("ai_controls_end_date", False),
        },
        "interaction_profile": {
            "preferred_tone": "balanced"
            if low_confidence
            else ("strict" if traits["strictness_affinity"] >= 70 else "balanced"),
            "control_frequency_hint": "high" if traits["accountability_need"] >= 70 else "medium",
            "novelty_hint": "high" if traits["novelty_affinity"] >= 70 else "medium",
            "autonomy_profile": default_limits.get("autonomy_profile", autonomy_profile),
            "autonomy_bias": default_limits.get("autonomy_bias", autonomy_bias),
            "praise_timing": psychogram["interaction_preferences"]["praise_timing"],
            "instruction_style": psychogram["interaction_preferences"]["instruction_style"],
        },
        "safety_filters": {
            "blocked_trigger_words": sorted(
                list(
                    {
                        *setup_session.get("blocked_trigger_words", []),
                        *[
                            token.strip()
                            for token in (psychogram.get("taboo_text") or "").replace(";", ",").split(",")
                            if token.strip()
                        ],
                    }
                )
            ),
            "forbidden_topics": setup_session.get("forbidden_topics", []),
        },
        "conservative_defaults": conservative,
    }


def _get_session_or_404(setup_session_id: str) -> dict:
    store = load_sessions()
    session = store.get(setup_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    return session


def _find_user_setup_session(
    store: dict[str, dict], user_id: str, allowed_statuses: set[str] | None = None
) -> tuple[str, dict] | tuple[None, None]:
    statuses = allowed_statuses or {"draft", "setup_in_progress", "configured"}
    candidates = [
        (sid, sess)
        for sid, sess in store.items()
        if sess.get("user_id") == user_id and sess.get("status") in statuses
    ]
    if not candidates:
        return (None, None)
    candidates.sort(key=lambda item: item[1].get("updated_at", item[1].get("created_at", "")), reverse=True)
    return candidates[0]


def _create_draft_setup_session(user_id: str, language: str = "de") -> dict:
    now = _now_iso()
    return {
        "setup_session_id": str(uuid4()),
        "user_id": user_id,
        "character_id": None,
        "status": "draft",
        "hard_stop_enabled": True,
        "autonomy_mode": "execute",
        "integrations": ["ttlock"],
        "language": _lang(language),
        "blocked_trigger_words": [],
        "forbidden_topics": [],
        "contract_start_date": None,
        "contract_end_date": None,
        "contract_min_end_date": None,
        "contract_max_end_date": None,
        "ai_controls_end_date": True,
        "max_penalty_per_day_minutes": 60,
        "max_penalty_per_week_minutes": 240,
        "opening_limit_period": "day",
        "max_openings_in_period": 1,
        "max_openings_per_day": 1,
        "opening_window_minutes": 30,
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "answers": [],
        "psychogram": None,
        "policy_preview": None,
        "active_session_id": None,
        "psychogram_analysis": None,
        "psychogram_analysis_status": "idle",
        "psychogram_analysis_generated_at": None,
        "contract_generation_status": "idle",
        "contract_generated_at": None,
        "ai_proposed_end_date": None,
        "created_at": now,
        "updated_at": now,
    }


def _get_db_session(request: Request):
    return request.app.state.db_session_factory()


def _require_user_token(user_id: str, auth_token: str, db, request: Request) -> User:
    token_user_id = _resolve_user_id_from_token(auth_token, request)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def _serialize_chastity_session(session: ChastitySession) -> dict:
    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "character_id": session.character_id,
        "status": session.status,
        "language": session.language,
        "policy": json.loads(session.policy_snapshot_json),
        "psychogram": json.loads(session.psychogram_snapshot_json),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


def _serialize_llm_profile(profile: LLMProfile) -> dict:
    return {
        "user_id": profile.user_id,
        "provider_name": profile.provider_name,
        "api_url": profile.api_url,
        "chat_model": profile.chat_model,
        "vision_model": profile.vision_model,
        "behavior_prompt": profile.behavior_prompt,
        "is_active": profile.is_active,
        "has_api_key": bool(profile.api_key_encrypted),
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


def _extract_pending_actions(narration: str) -> tuple[str, list[dict], list[dict]]:
    pattern = re.compile(r"\[\[ACTION:(?P<kind>[a-zA-Z0-9_\-]+)\|(?P<payload>\{.*?\})\]\]")
    file_pattern = re.compile(r"\[\[FILE\|(?P<payload>\{.*?\})\]\]")
    actions: list[dict] = []
    generated_files: list[dict] = []
    cleaned = narration
    for match in pattern.finditer(narration):
        action_type = match.group("kind")
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"raw": payload_text}
        actions.append({"action_type": action_type, "payload": payload, "requires_execute_call": True})
        cleaned = cleaned.replace(match.group(0), "").strip()
    for match in file_pattern.finditer(narration):
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"name": "response.txt", "mime_type": "text/plain", "content": payload_text}
        generated_files.append(
            {
                "name": str(payload.get("name", "response.txt")),
                "mime_type": str(payload.get("mime_type", "text/plain")),
                "content": str(payload.get("content", "")),
            }
        )
        cleaned = cleaned.replace(match.group(0), "").strip()
    return cleaned, actions, generated_files


def _sync_setup_snapshot_to_active_session(request: Request, setup_session: dict) -> bool:
    session_id = setup_session.get("active_session_id")
    if not session_id:
        return False
    db = _get_db_session(request)
    try:
        applied = _sync_setup_snapshot_to_active_session_db(db, setup_session)
        if not applied:
            return False
        db.commit()
        return True
    finally:
        db.close()


def _sync_setup_snapshot_to_active_session_db(db, setup_session: dict) -> bool:
    session_id = setup_session.get("active_session_id")
    if not session_id:
        return False
    db_session = db.get(ChastitySession, session_id)
    if db_session is None:
        return False
    db_session.psychogram_snapshot_json = json.dumps(setup_session["psychogram"])
    db_session.policy_snapshot_json = json.dumps(setup_session["policy_preview"])
    db_session.updated_at = datetime.now(UTC)
    db.add(db_session)
    return True


def _build_ai_context_summary(psychogram: dict, policy: dict) -> str:
    traits = psychogram.get("traits", {})
    top_traits = ", ".join(
        f"{name}:{score}"
        for name, score in sorted(traits.items(), key=lambda item: item[1], reverse=True)[:4]
    )
    interaction = psychogram.get("interaction_preferences", {})
    safety = psychogram.get("safety_profile", {})
    personal = psychogram.get("personal_preferences", {})
    hard_limits = str(psychogram.get("hard_limits_text") or psychogram.get("taboo_text") or "").strip()
    soft_limits = str(psychogram.get("soft_limits_text") or _fixed_soft_limits_text("de")).strip()
    generated_contract = (policy or {}).get("generated_contract", {}) or {}
    contract_consent = generated_contract.get("consent", {}) if isinstance(generated_contract, dict) else {}
    consent_required = str(contract_consent.get("required_text") or "")
    consent_accepted = bool(contract_consent.get("accepted"))
    consent_accepted_at = str(contract_consent.get("accepted_at") or "")
    consent_state = (
        f"accepted@{consent_accepted_at or '-'}"
        if consent_accepted
        else f"pending(required='{consent_required or '-'}')"
    )
    limits = (policy or {}).get("limits", {})
    interaction_policy = (policy or {}).get("interaction_profile", {})

    safety_mode = safety.get("mode", "safeword")
    safety_text = f"mode={safety_mode}"
    abort_protocol = None
    if safety_mode == "safeword" and safety.get("safeword"):
        safety_text = f"{safety_text}, safeword={safety.get('safeword')}"
        abort_protocol = safety.get("safeword_abort_protocol")
    if safety_mode == "traffic_light" and isinstance(safety.get("traffic_light_words"), dict):
        tl = safety.get("traffic_light_words")
        safety_text = f"{safety_text}, tl={tl.get('green','')}/{tl.get('yellow','')}/{tl.get('red','')}"
        abort_protocol = safety.get("red_abort_protocol")
    if isinstance(abort_protocol, dict):
        q_count = int(abort_protocol.get("confirmation_questions_required", 2))
        reason_required = bool(abort_protocol.get("reason_required", True))
        safety_text = f"{safety_text}, emergency_abort=immediate_after_{q_count}_checks(reason_required={reason_required})"

    return (
        f"summary={psychogram.get('summary', 'n/a')}; "
        f"top_traits={top_traits or 'n/a'}; "
        f"instruction_style={interaction.get('instruction_style', 'mixed')}; "
        f"escalation_mode={interaction.get('escalation_mode', 'moderate')}; "
        f"experience={interaction.get('experience_level', 5)}/"
        f"{interaction.get('experience_profile', 'intermediate')}; "
        f"grooming_preference={personal.get('grooming_preference', 'no_preference')}; "
        f"hard_limits={hard_limits or '-'}; "
        f"soft_limits={soft_limits or '-'}; "
        f"contract_consent={consent_state}; "
        f"safety={safety_text}; "
        f"tone={interaction_policy.get('preferred_tone', 'balanced')}; "
        f"intensity={limits.get('max_intensity_level', 2)}; "
        f"hard_stop={policy.get('hard_stop_enabled', True)}"
    )



def _generate_ai_narration_for_session(
    db, request: Request, session: ChastitySession, action: str, language: str, attachments: list[dict] | None = None
) -> str:
    psychogram = json.loads(session.psychogram_snapshot_json)
    policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
    psychogram_summary = _build_ai_context_summary(psychogram, policy)

    ai_service = request.app.state.ai_service
    recent_turns = (
        db.scalars(
            select(Turn)
            .where(Turn.session_id == session.id)
            .order_by(Turn.turn_no.desc())
            .limit(6)
        )
        .all()
    )
    recent_turns = list(reversed(recent_turns))
    history_lines: list[str] = []
    for turn in recent_turns:
        history_lines.append(f"Wearer: {turn.player_action}")
        history_lines.append(f"Keyholder: {turn.ai_narration}")
    history_block = "\n".join(history_lines).strip()
    attachment_names = [str(item.get("name", "file")) for item in (attachments or [])]
    attachment_hint = f"\nCurrent attachments: {', '.join(attachment_names)}" if attachment_names else ""
    action_with_context = (
        (f"Recent dialogue:\n{history_block}\n\nCurrent wearer input: {action}{attachment_hint}")
        if history_block
        else f"Current wearer input: {action}{attachment_hint}"
    )

    context = StoryTurnContext(
        session_id=session.id,
        action=action_with_context,
        language=language,
        psychogram_summary=psychogram_summary,
    )
    profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == session.user_id))
    if profile is not None and profile.is_active and hasattr(ai_service, "generate_narration_with_profile"):
        has_images = any(str(item.get("type", "")).startswith("image/") for item in (attachments or []))
        selected_model = profile.vision_model if has_images and profile.vision_model else profile.chat_model
        try:
            api_key = decrypt_secret(profile.api_key_encrypted, request.app.state.config.SECRET_KEY)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Stored API key cannot be decrypted with current SECRET_KEY. "
                    "Please save the LLM profile again with a fresh API key."
                ),
            ) from exc
        return ai_service.generate_narration_with_profile(
            context,
            api_url=profile.api_url,
            api_key=api_key,
            chat_model=selected_model,
            behavior_prompt=profile.behavior_prompt,
            attachments=attachments or [],
        )
    return ai_service.generate_narration(context)


def _generate_ai_narration_for_setup_preview(
    db,
    request: Request,
    user_id: str,
    action: str,
    language: str,
    psychogram: dict,
    policy: dict,
    attachments: list[dict] | None = None,
) -> str:
    ai_service = request.app.state.ai_service
    context = StoryTurnContext(
        session_id="setup-preview",
        action=action,
        language=language,
        psychogram_summary=_build_ai_context_summary(psychogram, policy),
    )
    profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == user_id))
    if profile is not None and profile.is_active and hasattr(ai_service, "generate_narration_with_profile"):
        has_images = any(str(item.get("type", "")).startswith("image/") for item in (attachments or []))
        selected_model = profile.vision_model if has_images and profile.vision_model else profile.chat_model
        try:
            api_key = decrypt_secret(profile.api_key_encrypted, request.app.state.config.SECRET_KEY)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Stored API key cannot be decrypted with current SECRET_KEY. "
                    "Please save the LLM profile again with a fresh API key."
                ),
            ) from exc
        return ai_service.generate_narration_with_profile(
            context,
            api_url=profile.api_url,
            api_key=api_key,
            chat_model=selected_model,
            behavior_prompt=profile.behavior_prompt,
            attachments=attachments or [],
        )
    return ai_service.generate_narration(context)


def _generate_psychogram_analysis_for_setup(db, request: Request, setup_session: dict) -> str:
    analysis, _proposed_end_date = _generate_psychogram_analysis_with_end_date_for_setup(db, request, setup_session)
    return analysis


def _is_provider_error_text(text: str | None) -> bool:
    if not text:
        return False
    normalized = str(text).strip().lower()
    markers = [
        "provider-anfrage fehlgeschlagen",
        "der provider hat die anfrage abgelehnt",
        "provider request failed",
        "provider rejected the request",
        "provider timeout",
        "provider-timeout",
        "llm-anfrage unerwartet fehlgeschlagen",
        "llm request failed unexpectedly",
    ]
    return any(marker in normalized for marker in markers)


def _default_proposed_end_date(setup_session: dict) -> str | None:
    contract = (setup_session.get("policy_preview") or {}).get("contract") or {}
    if contract.get("end_date"):
        return str(contract.get("end_date"))
    if contract.get("max_end_date"):
        return str(contract.get("max_end_date"))
    if contract.get("min_end_date"):
        return str(contract.get("min_end_date"))
    return None


def _normalize_proposed_end_date(raw_value: str | None, setup_session: dict) -> str | None:
    if not raw_value:
        return _default_proposed_end_date(setup_session)
    value = str(raw_value).strip()
    upper = value.upper()
    if upper in {"AI_DECIDES", "KI_ENTSCHEIDET", "KI-ENTSCHEIDET"}:
        return None

    contract = (setup_session.get("policy_preview") or {}).get("contract") or {}
    try:
        candidate = date.fromisoformat(value)
    except ValueError:
        return _default_proposed_end_date(setup_session)

    try:
        min_end = date.fromisoformat(contract["min_end_date"]) if contract.get("min_end_date") else None
    except ValueError:
        min_end = None
    try:
        max_end = date.fromisoformat(contract["max_end_date"]) if contract.get("max_end_date") else None
    except ValueError:
        max_end = None
    if min_end and candidate < min_end:
        candidate = min_end
    if max_end and candidate > max_end:
        candidate = max_end
    return candidate.isoformat()


def _extract_proposed_end_date(raw_text: str, setup_session: dict) -> tuple[str, str | None]:
    text = (raw_text or "").strip()
    match = re.search(
        r"(?:PROPOSED_END_DATE|VORGESCHLAGENES_ENDDATUM)\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|AI_DECIDES|KI_ENTSCHEIDET)",
        text,
        flags=re.IGNORECASE,
    )
    proposed = _normalize_proposed_end_date(match.group(1) if match else None, setup_session)
    cleaned = text
    if match:
        cleaned = re.sub(
            r"(?:PROPOSED_END_DATE|VORGESCHLAGENES_ENDDATUM)\s*:\s*(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|AI_DECIDES|KI_ENTSCHEIDET)\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
    if not cleaned:
        cleaned = text or "-"
    return cleaned, proposed


def _generate_psychogram_analysis_with_end_date_for_setup(
    db, request: Request, setup_session: dict
) -> tuple[str, str | None]:
    psychogram = setup_session.get("psychogram") or {}
    policy = setup_session.get("policy_preview") or {}
    contract = policy.get("contract") or {}
    lang = _lang(setup_session.get("language", "de"))
    action = (
        (
            "Analyze this psychogram for dashboard summary. Provide concise guidance: tone, boundaries, intensity and first steps. "
            f"Choose a provisional session end date within this contract window: start={contract.get('start_date')}, "
            f"min_end={contract.get('min_end_date')}, max_end={contract.get('max_end_date')}. "
            "First line MUST be exactly: PROPOSED_END_DATE: YYYY-MM-DD or PROPOSED_END_DATE: AI_DECIDES."
        )
        if lang == "en"
        else (
            "Analysiere dieses Psychogramm fÃ¼r eine Dashboard-Zusammenfassung. Gib kurze Hinweise zu Ton, Grenzen, IntensitÃ¤t und ersten Schritten. "
            f"WÃ¤hle ein vorlÃ¤ufiges Session-Enddatum innerhalb dieses Vertragsfensters: start={contract.get('start_date')}, "
            f"min_end={contract.get('min_end_date')}, max_end={contract.get('max_end_date')}. "
            "Die erste Zeile MUSS exakt sein: VORGESCHLAGENES_ENDDATUM: YYYY-MM-DD oder VORGESCHLAGENES_ENDDATUM: KI_ENTSCHEIDET."
        )
    )
    try:
        raw = _generate_ai_narration_for_setup_preview(
            db,
            request,
            setup_session["user_id"],
            action,
            lang,
            psychogram,
            policy,
        )
        if _is_provider_error_text(raw):
            raise RuntimeError(str(raw))
        analysis, proposed_end_date = _extract_proposed_end_date(raw, setup_session)
        return analysis, proposed_end_date
    except Exception:
        interaction = psychogram.get("interaction_preferences", {})
        safety = psychogram.get("safety_profile", {})
        fallback_text = (
            f"Profilanalyse: escalation={interaction.get('escalation_mode', 'moderate')}, "
            f"experience={interaction.get('experience_profile', 'intermediate')}, "
            f"safety={safety.get('mode', 'safeword')}."
        )
        return fallback_text, _default_proposed_end_date(setup_session)


def _contract_template_path(lang: str) -> Path:
    root = Path(__file__).resolve().parents[3]
    filename = "CONTRACT_TEMPLATE_EN.md" if _lang(lang) == "en" else "CONTRACT_TEMPLATE_DE.md"
    return root / "docs" / "templates" / filename


def _strip_front_matter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return text
    return text[end_idx + 5 :].lstrip()


def _contract_bool_text(value: bool, lang: str) -> str:
    if _lang(lang) == "en":
        return "enabled" if value else "disabled"
    return "aktiviert" if value else "deaktiviert"


def _days_between(start_raw: str | None, end_raw: str | None) -> int:
    try:
        if not start_raw or not end_raw:
            return 0
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
        return max(0, (end - start).days)
    except Exception:
        return 0


def _setup_user_display_name(setup_session: dict) -> str:
    for key in ("user_display_name", "display_name", "username"):
        value = str(setup_session.get(key) or "").strip()
        if value:
            return value
    fallback = str(setup_session.get("user_id") or "").strip()
    return fallback or "sub"


def _build_contract_template_fields(setup_session: dict) -> dict[str, str]:
    lang = _lang(setup_session.get("language", "de"))
    policy = setup_session.get("policy_preview") or {}
    psychogram = setup_session.get("psychogram") or {}
    contract = policy.get("contract") or {}
    limits = policy.get("limits") or {}
    interaction_profile = policy.get("interaction_profile") or {}
    interaction = psychogram.get("interaction_preferences") or {}
    safety = psychogram.get("safety_profile") or {}
    personal = psychogram.get("personal_preferences") or {}
    consent = ((policy.get("generated_contract") or {}).get("consent") or {})
    consent_accepted = bool(consent.get("accepted"))
    consent_text = str(consent.get("consent_text") or "").strip()
    consent_accepted_at = str(consent.get("accepted_at") or "").strip()

    proposed_end = contract.get("proposed_end_date") or ("AI-decides" if lang == "en" else "KI-entscheidet")
    safety_mode = str(safety.get("mode", "safeword"))
    safeword = str(safety.get("safeword", "")) if safety_mode == "safeword" else "-"
    traffic_words = "-"
    traffic_red_protocol_text = ""
    emergency_abort_suffix = ""
    emergency_abort_termination = ""
    if safety_mode == "safeword":
        safeword_abort = safety.get("safeword_abort_protocol") or {}
        question_count = int(safeword_abort.get("confirmation_questions_required", 2))
        if lang == "de":
            emergency_abort_suffix = (
                f" Beim Safeword gilt sofortiger Sitzungsabbruch als Notfallprotokoll. "
                f"Vor der Ausfuehrung sind {question_count} Kontrollfragen Pflicht; "
                "mindestens eine muss eine Begruendung enthalten."
            )
            emergency_abort_termination = (
                " Safeword-Notfallabbruch erfolgt nach zweistufiger Kontrollabfrage mit Begruendungspflicht."
            )
        else:
            emergency_abort_suffix = (
                f" On safeword, immediate session abort applies as emergency protocol. "
                f"Before execution, {question_count} control questions are mandatory; "
                "at least one must include a reason."
            )
            emergency_abort_termination = (
                " Safeword emergency abort executes after a two-step control check with mandatory reason."
            )
    elif safety_mode == "traffic_light":
        tl = safety.get("traffic_light_words") or {"green": "green", "yellow": "yellow", "red": "red"}
        traffic_words = f"{tl.get('green', 'green')}/{tl.get('yellow', 'yellow')}/{tl.get('red', 'red')}"
        red_abort = safety.get("red_abort_protocol") or {}
        question_count = int(red_abort.get("confirmation_questions_required", 2))
        if lang == "de":
            traffic_red_protocol_text = (
                f" Bei ROT gilt sofortiger Sitzungsabbruch als Notfallprotokoll. "
                f"Vor der Ausfuehrung sind {question_count} Kontrollfragen Pflicht; "
                "mindestens eine muss eine Begruendung enthalten."
            )
            emergency_abort_termination = (
                " ROT-Notfallabbruch erfolgt nach zweistufiger Kontrollabfrage mit Begruendungspflicht."
            )
        else:
            traffic_red_protocol_text = (
                f" On RED, immediate session abort applies as emergency protocol. "
                f"Before execution, {question_count} control questions are mandatory; "
                "at least one must include a reason."
            )
            emergency_abort_termination = (
                " RED emergency abort executes after a two-step control check with mandatory reason."
            )

    hard_limits = str(psychogram.get("hard_limits_text") or psychogram.get("taboo_text") or "").strip()
    if not hard_limits:
        hard_limits = (
            "Keine bleibenden koerperlichen Schaeden; keine oeffentliche Blossstellung."
            if lang == "de"
            else "No permanent physical harm; no public humiliation."
        )
    soft_limits = str(psychogram.get("soft_limits_text") or _fixed_soft_limits_text(lang)).strip()
    if not soft_limits:
        soft_limits = _fixed_soft_limits_text(lang)

    min_duration_days = _days_between(contract.get("start_date"), contract.get("min_end_date"))
    integrations = ", ".join(policy.get("integrations", [])) or "ttlock"
    end_control_mode = (
        "AI-controlled; Keyholder may adjust provisional end date anytime within min/max boundaries."
        if lang == "en"
        else "KI-gesteuert; die Keyholderin darf das vorlaeufige Enddatum jederzeit innerhalb der Min/Max-Grenzen anpassen."
    )
    if not contract.get("ai_controls_end_date"):
        end_control_mode = "fixed/manual" if lang == "en" else "fix/manuell"
    user_display_name = _setup_user_display_name(setup_session)

    fields: dict[str, str] = {
        "session_id": str(setup_session.get("active_session_id") or "-"),
        "setup_session_id": str(setup_session.get("setup_session_id") or "-"),
        "contract_version": "1.0.1",
        "generated_at_iso": _now_iso(),
        "generated_by": "ai_template_renderer",
        "contract_start_date": str(contract.get("start_date") or "-"),
        "contract_min_end_date": str(contract.get("min_end_date") or "-"),
        "contract_max_end_date": str(contract.get("max_end_date") or "-"),
        "proposed_end_date_ai": str(proposed_end),
        "end_date_control_mode": end_control_mode,
        "min_duration_days": str(min_duration_days),
        "max_extension_per_incident_days": "2",
        "hard_stop_enabled": _contract_bool_text(bool(policy.get("hard_stop_enabled", True)), lang),
        "pause_policy": (
            "Nur bei medizinischen/emotionalen Gruenden und dokumentierter Freigabe."
            if lang == "de"
            else "Only for medical/emotional reasons with documented release."
        ),
        "daily_checkin_required": ("ja" if lang == "de" else "yes"),
        "inspection_frequency_policy": str(interaction_profile.get("control_frequency_hint") or "medium"),
        "max_openings_in_period": str(limits.get("max_openings_in_period", "-")),
        "opening_limit_period": str(limits.get("opening_limit_period", "day")),
        "opening_window_minutes": str(limits.get("opening_window_minutes", "-")),
        "max_penalty_per_day_minutes": str(limits.get("max_penalty_per_day_minutes", "-")),
        "max_penalty_per_week_minutes": str(limits.get("max_penalty_per_week_minutes", "-")),
        "reward_policy": (
            "Situative Anerkennung, ggf. Verkuerzung/Erleichterung bei konsistentem Gehorsam."
            if lang == "de"
            else "Situational recognition, optional shortening/easing for consistent obedience."
        ),
        "penalty_policy": (
            "Konsequenzen sind praezise, nachvollziehbar und innerhalb definierter Caps."
            if lang == "de"
            else "Consequences are precise, traceable, and within configured caps."
        ),
        "safety_mode": safety_mode,
        "safeword": safeword,
        "traffic_light_words": traffic_words,
        "hard_limits_text": hard_limits,
        "soft_limits_text": soft_limits,
        "health_protocol": (
            "Bei Warnzeichen sofort pausieren/abbrechen und Zustand melden."
            if lang == "de"
            else "Immediately pause/stop and report status when warning signs appear."
        )
        + traffic_red_protocol_text
        + emergency_abort_suffix,
        "psychogram_summary": str(psychogram.get("summary") or "-"),
        "psychogram_analysis": str(setup_session.get("psychogram_analysis") or psychogram.get("analysis") or "-"),
        "instruction_style": str(interaction.get("instruction_style") or "mixed"),
        "escalation_mode": str(interaction.get("escalation_mode") or "moderate"),
        "experience_profile": str(interaction.get("experience_profile") or "intermediate"),
        "grooming_preference": str(personal.get("grooming_preference") or "no_preference"),
        "tone_profile": str(interaction_profile.get("preferred_tone") or "balanced"),
        "integrations": integrations,
        "autonomy_mode": str(policy.get("autonomy_mode") or "execute"),
        "action_execution_mode": (
            "execute_with_audit" if str(policy.get("autonomy_mode") or "execute") == "execute" else "suggest_first"
        ),
        "audit_enabled": ("ja" if lang == "de" else "yes"),
        "amendment_policy": (
            "Aenderungen werden auditierbar dokumentiert und von beiden Seiten bestaetigt."
            if lang == "de"
            else "Changes are audit-logged and confirmed by both sides."
        ),
        "termination_policy": (
            "Ende bei Vertragsdatum, Safety-Stop oder gegenseitiger Einigung."
            if lang == "de"
            else "Ends at contract date, safety stop, or mutual agreement."
        )
        + emergency_abort_termination,
        "debrief_policy": (
            "Nachbesprechung erfolgt im Session-Verlauf."
            if lang == "de"
            else "Debrief is handled during the session flow."
        ),
        "sub_name": user_display_name,
        "user_name": user_display_name,
        "keyholder_name": "AI Keyholder",
        "signature_date_sub": (
            consent_accepted_at[:10]
            if consent_accepted and consent_accepted_at
            else str(contract.get("start_date") or date.today().isoformat())
        ),
        "signature_sub": (
            ("[digitally signed]" if lang == "en" else "[digital signiert]")
            if consent_accepted
            else ("[signature pending]" if lang == "en" else "[signatur ausstehend]")
        ),
        "signature_date_keyholder": str(contract.get("start_date") or date.today().isoformat()),
        "signature_keyholder": "[digital consent]",
        "consent_required_text": str(consent.get("required_text") or _required_contract_consent_text(lang)),
        "consent_accepted": "true" if consent_accepted else "false",
        "consent_text": consent_text or "-",
        "consent_accepted_at": consent_accepted_at or "-",
    }
    return fields


def _render_contract_template(setup_session: dict) -> str:
    lang = _lang(setup_session.get("language", "de"))
    template_path = _contract_template_path(lang)
    try:
        raw_template = template_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    template = _strip_front_matter(raw_template)
    fields = _build_contract_template_fields(setup_session)

    def replace(match: re.Match) -> str:
        key = match.group(1)
        value = str(fields.get(key, "-")).strip()
        return value if value else "-"

    return re.sub(r"\{\{([a-zA-Z0-9_]+)\}\}", replace, template)


def _looks_like_contract_text(text: str, lang: str) -> bool:
    content = (text or "").strip()
    if len(content) < 350:
        return False
    if _lang(lang) == "en":
        return ("Article 1" in content) and ("Signature" in content)
    return ("Artikel 1" in content) and ("Signatur" in content)


def _build_contract_fallback_text(setup_session: dict) -> str:
    rendered = _render_contract_template(setup_session)
    return rendered.strip() if rendered.strip() else "Contract template unavailable."


def _generate_contract_for_setup(db, request: Request, setup_session: dict) -> str:
    psychogram = setup_session.get("psychogram") or {}
    policy = setup_session.get("policy_preview") or {}
    lang = _lang(setup_session.get("language", "de"))
    contract = policy.get("contract") or {}
    analysis = setup_session.get("psychogram_analysis") or psychogram.get("analysis") or ""
    draft = _build_contract_fallback_text(setup_session)
    if not draft.strip():
        return "Contract draft unavailable."

    action = (
        (
            "You are revising a generated chastity contract draft. "
            "You may refine wording and add short useful clarifications when necessary. "
            "Do not remove safety rules, contract dates, or article structure. "
            "Keep markdown and keep headings/articles intact. "
            f"The provisional end date is {contract.get('proposed_end_date') or 'AI-decides'} and may be adjusted by the keyholder within min/max bounds. "
            f"Psychogram analysis context: {analysis}\n\n"
            "DRAFT CONTRACT:\n"
            f"{draft}"
        )
        if lang == "en"
        else (
            "Du ueberarbeitest einen erzeugten Keuschheitsvertrag-Entwurf. "
            "Du darfst Formulierungen verbessern und bei Bedarf kurze sinnvolle Klarstellungen ergaenzen. "
            "Sicherheitsregeln, Vertragsdaten und Artikelstruktur duerfen nicht entfernt werden. "
            "Markdown beibehalten, Ueberschriften/Artikel intakt lassen. "
            f"Das vorlaeufige Enddatum ist {contract.get('proposed_end_date') or 'KI-entscheidet'} und darf durch die Keyholderin innerhalb der Min/Max-Grenzen angepasst werden. "
            f"Kontext Psychogramm-Analyse: {analysis}\n\n"
            "VERTRAGS-ENTWURF:\n"
            f"{draft}"
        )
    )
    try:
        raw = _generate_ai_narration_for_setup_preview(
            db,
            request,
            setup_session["user_id"],
            action,
            lang,
            psychogram,
            policy,
        )
        if _is_provider_error_text(raw):
            raise RuntimeError(str(raw))
        if not _looks_like_contract_text(raw, lang):
            raise RuntimeError("contract format validation failed")
        return raw.strip()
    except Exception:
        return draft


from chastease.api.routers import (
    auth_router,
    chat_router,
    llm_router,
    sessions_router,
    setup_router,
    story_router,
    system_router,
    users_router,
)

api_router.include_router(auth_router)
api_router.include_router(llm_router)
api_router.include_router(users_router)
api_router.include_router(story_router)
api_router.include_router(chat_router)
api_router.include_router(setup_router)
api_router.include_router(sessions_router)
api_router.include_router(system_router)

