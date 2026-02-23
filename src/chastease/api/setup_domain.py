from datetime import UTC, date, datetime, timedelta
import json
import re
from uuid import uuid4

from fastapi import HTTPException

from chastease.api.questionnaire import (
    QUESTIONNAIRE_VERSION,
    QUESTION_BANK,
    QUESTION_IDS,
    SUPPORTED_LANGUAGES,
    TRAIT_KEYS,
    TRANSLATIONS,
)
from chastease.repositories.setup_store import load_sessions
def _lang(value: str) -> str:
    return value if value in SUPPORTED_LANGUAGES else "de"

def _t(lang: str, key: str) -> str:
    return TRANSLATIONS[_lang(lang)][key]

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()

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
    lang = _lang(setup_session.get("language", "de"))
    policy = setup_session.get("policy_preview") or {}
    contract = policy.get("contract") or {}
    consent = ((policy.get("generated_contract") or {}).get("consent") or {})
    consent_accepted = bool(consent.get("accepted"))
    consent_text = str(consent.get("consent_text") or "").strip() or "-"
    consent_accepted_at = str(consent.get("accepted_at") or "").strip() or "-"
    signature_date_sub = (
        str(consent_accepted_at[:10])
        if consent_accepted and consent_accepted_at != "-"
        else str(contract.get("start_date") or date.today().isoformat())
    )
    signature_sub = (
        ("[digitally signed]" if lang == "en" else "[digital signiert]")
        if consent_accepted
        else ("[signature pending]" if lang == "en" else "[signatur ausstehend]")
    )

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
        "consent_accepted": "true" if consent_accepted else "false",
        "consent_text": consent_text,
        "consent_accepted_at": consent_accepted_at,
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
        "integration_config": setup_session.get("integration_config", {}),
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
        "integrations": [],
        "integration_config": {},
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
