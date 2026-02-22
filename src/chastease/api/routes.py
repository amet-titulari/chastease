from datetime import UTC, date, datetime, timedelta
import base64
import json
import hashlib
import hmac
import re
import secrets
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from chastease.models import Character, ChastitySession, LLMProfile, Turn, User
from chastease.repositories.setup_store import load_sessions, save_sessions
from chastease.shared.secrets_crypto import decrypt_secret, encrypt_secret
from chastease.services.ai.base import StoryTurnContext

api_router = APIRouter()
auth_tokens: dict[str, str] = {}

QUESTIONNAIRE_VERSION = "setup-q-v2.4"
SUPPORTED_LANGUAGES = {"de", "en"}

TRANSLATIONS = {
    "de": {
        "not_found": "Setup-Session nicht gefunden.",
        "not_editable": "Setup-Session ist nicht mehr bearbeitbar.",
        "cannot_complete": "Setup-Session kann nicht abgeschlossen werden.",
        "not_enough_answers": "Zu wenige Antworten zum Abschliessen des Setups.",
        "unknown_question": "Unbekannte Frage-ID",
        "action_required": "Feld 'action' ist erforderlich.",
        "story_prefix": "Du versuchst",
        "demo_title": "Setup Prototype Demo",
        "demo_hint": "Teste hier den Setup-Flow vor der DB-Persistenz.",
        "summary_template": "Struktur {structure}, Strenge {strictness}, Kontrolle {accountability}.",
        "recalibration_done": "Psychogramm wurde aktualisiert.",
    },
    "en": {
        "not_found": "Setup session not found.",
        "not_editable": "Setup session is not editable.",
        "cannot_complete": "Setup session cannot be completed.",
        "not_enough_answers": "Not enough answers to complete setup.",
        "unknown_question": "Unknown question_id",
        "action_required": "Field 'action' is required.",
        "story_prefix": "You attempt",
        "demo_title": "Setup Prototype Demo",
        "demo_hint": "Use this page to test the setup flow before DB persistence.",
        "summary_template": "Structure {structure}, strictness {strictness}, accountability {accountability}.",
        "recalibration_done": "Psychogram has been updated.",
    },
}

# Inspired by psychometric preference tests; intentionally authored, not copied.
QUESTION_BANK = [
    {
        "id": "q1_rule_structure",
        "type": "scale_100",
        "texts": {
            "de": "Wie wichtig sind dir klare, schriftliche Regeln und genau definierte Erwartungen?",
            "en": "How important are clear written rules and well-defined expectations to you?",
        },
        "weights": {"structure_need": 1.0, "protocol_affinity": 0.4},
    },
    {
        "id": "q2_strictness_authority",
        "type": "scale_100",
        "texts": {
            "de": "Wie stark moechtest du in dieser Session Strenge, Konsequenz und Autoritaet erleben?",
            "en": "How strongly do you want to experience strictness, consequences, and authority in this session?",
        },
        "weights": {"strictness_affinity": 1.0, "accountability_need": 0.3},
    },
    {
        "id": "q3_control_need",
        "type": "scale_100",
        "texts": {
            "de": "Wie sehr brauchst du das Gefuehl, wirklich kontrolliert und ueberwacht zu werden?",
            "en": "How much do you need to feel genuinely controlled and monitored?",
        },
        "weights": {"accountability_need": 1.0, "structure_need": 0.3},
    },
    {
        "id": "q4_praise_importance",
        "type": "scale_100",
        "texts": {
            "de": "Wie wichtig ist positives Feedback/Anerkennung fuer gutes Verhalten?",
            "en": "How important is positive feedback/recognition for good behavior?",
        },
        "weights": {"praise_affinity": 1.0},
    },
    {
        "id": "q5_novelty_challenge",
        "type": "scale_100",
        "texts": {
            "de": "Wie sehr suchst du Abwechslung, neue Aufgaben und ungewohnte Herausforderungen?",
            "en": "How much are you looking for variety, new tasks, and unfamiliar challenges?",
        },
        "weights": {"novelty_affinity": 0.7, "challenge_affinity": 0.7},
    },
    {
        "id": "q6_intensity_1_5",
        "type": "scale_100",
        "texts": {
            "de": "Welche Intensitaet passt aktuell am besten?",
            "en": "What intensity fits best right now?",
        },
        "weights": {"strictness_affinity": 0.8, "challenge_affinity": 0.6},
    },
    {
        "id": "q8_instruction_style",
        "type": "choice",
        "texts": {
            "de": "Wie sollen Anweisungen am liebsten gegeben werden?",
            "en": "How should instructions preferably be delivered?",
        },
        "options": [
            {"value": "direct_command", "de": "direkt & befehlsartig", "en": "direct & command-like"},
            {"value": "polite_authoritative", "de": "hoeflich-autoritaer", "en": "polite-authoritative"},
            {"value": "suggestive", "de": "suggestiv/verfuehrerisch", "en": "suggestive/seductive"},
            {"value": "mixed", "de": "gemischt je nach Situation", "en": "mixed depending on situation"},
        ],
        "weights": {},
    },
    {
        "id": "q11_escalation_mode",
        "type": "choice",
        "texts": {
            "de": "Wie schnell soll Intensitaet eskalieren?",
            "en": "How quickly should intensity escalate?",
        },
        "options": [
            {"value": "very_slow", "de": "sehr langsam", "en": "very slow"},
            {"value": "slow", "de": "langsam", "en": "slow"},
            {"value": "moderate", "de": "moderat", "en": "moderate"},
            {"value": "strong", "de": "stark", "en": "strong"},
            {"value": "aggressive", "de": "aggressiv", "en": "aggressive"},
        ],
        "weights": {},
    },
    {
        "id": "q12_grooming_preference",
        "type": "choice",
        "texts": {
            "de": "Welche Intimrasur-Praeferenz soll beachtet werden?",
            "en": "Which grooming preference should be respected?",
        },
        "options": [
            {"value": "no_preference", "de": "keine Praeferenz", "en": "no preference"},
            {"value": "clean_shaven", "de": "glatt rasiert", "en": "clean shaven"},
            {"value": "trimmed", "de": "getrimmt", "en": "trimmed"},
            {"value": "natural", "de": "natuerlich", "en": "natural"},
        ],
        "weights": {},
    },
    {
        "id": "q7_taboo_text",
        "type": "text",
        "texts": {
            "de": "Gibt es Themen/Handlungen/Worte/Szenarien, die komplett tabu sind? (Freitext)",
            "en": "Are there topics/actions/words/scenarios that are completely taboo? (Free text)",
        },
        "weights": {},
    },
    {
        "id": "q10_safety_mode",
        "type": "choice",
        "texts": {
            "de": "Welches Sicherheitssystem soll verwendet werden?",
            "en": "Which safety system should be used?",
        },
        "options": [
            {"value": "safeword", "de": "Safeword", "en": "Safeword"},
            {"value": "traffic_light", "de": "Ampelsystem", "en": "Traffic light"},
        ],
        "weights": {},
    },
    {
        "id": "q10_safeword",
        "type": "text",
        "texts": {
            "de": "Safeword (nur bei safety_mode=safeword)",
            "en": "Safeword (only when safety_mode=safeword)",
        },
        "weights": {},
    },
    {
        "id": "q13_experience_level",
        "type": "scale_100",
        "texts": {
            "de": "Wie erfahren bist du in diesem Kontext?",
            "en": "How experienced are you in this context?",
        },
        "weights": {},
    },
    {
        "id": "q9_open_context",
        "type": "text",
        "texts": {
            "de": "Gibt es etwas, das ich unbedingt wissen sollte, bevor wir starten? (Offen)",
            "en": "Is there anything I should absolutely know before we start? (Open)",
        },
        "weights": {},
    },
]

QUESTION_IDS = [q["id"] for q in QUESTION_BANK]
TRAIT_KEYS = [
    "structure_need",
    "strictness_affinity",
    "challenge_affinity",
    "praise_affinity",
    "accountability_need",
    "novelty_affinity",
    "service_orientation",
    "protocol_affinity",
]


class StoryTurnRequest(BaseModel):
    action: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    session_id: str | None = None


class ChatTurnRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    attachments: list[dict] = Field(default_factory=list)


class SetupChatPreviewRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    message: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    attachments: list[dict] = Field(default_factory=list)


class ChatActionExecuteRequest(BaseModel):
    session_id: str = Field(min_length=1)
    action_type: str = Field(min_length=2)
    payload: dict = Field(default_factory=dict)


class ChatVisionReviewRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    language: Literal["de", "en"] = "de"
    picture_name: str = Field(default="image")
    picture_content_type: str = Field(default="image/jpeg")
    picture_data_url: str = Field(min_length=20)


class SetupStartRequest(BaseModel):
    user_id: str = Field(min_length=1)
    character_id: str | None = None
    auth_token: str = Field(min_length=8)
    hard_stop_enabled: bool = True
    autonomy_mode: Literal["execute", "suggest"] = "execute"
    integrations: list[Literal["ttlock", "chaster", "emlalock"]] = Field(default_factory=list)
    language: Literal["de", "en"] = "de"
    blocked_trigger_words: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    contract_start_date: str | None = None
    contract_end_date: str | None = None  # legacy fixed end date
    contract_max_end_date: str | None = None
    ai_controls_end_date: bool = True
    max_penalty_per_day_minutes: int = Field(default=60, ge=0, le=1440)
    max_penalty_per_week_minutes: int = Field(default=240, ge=0, le=10080)
    opening_limit_period: Literal["day", "week", "month"] = "day"
    max_openings_in_period: int = Field(default=1, ge=0, le=200)
    max_openings_per_day: int | None = Field(default=None, ge=0, le=10)  # legacy alias
    opening_window_minutes: int = Field(default=30, ge=1, le=240)


class SetupAnswer(BaseModel):
    question_id: str
    value: int | str


class SetupAnswersRequest(BaseModel):
    answers: list[SetupAnswer]


class PsychogramRecalibrationRequest(BaseModel):
    update_reason: str = Field(min_length=3)
    trait_overrides: dict[str, int] = Field(default_factory=dict)


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    display_name: str = Field(min_length=1)


class CharacterCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    strength: int = Field(default=5, ge=1, le=10)
    intelligence: int = Field(default=5, ge=1, le=10)
    charisma: int = Field(default=5, ge=1, le=10)
    hp: int = Field(default=100, ge=1, le=1000)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3)
    email: str = Field(min_length=5)
    display_name: str | None = None
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)


class LLMProfileUpsertRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    provider_name: str = Field(default="custom", min_length=2)
    api_url: str = Field(min_length=8)
    api_key: str | None = None
    chat_model: str = Field(min_length=2)
    vision_model: str | None = None
    behavior_prompt: str = Field(default="", min_length=0)
    is_active: bool = True


class LLMProfileTestRequest(BaseModel):
    user_id: str = Field(min_length=1)
    auth_token: str = Field(min_length=8)
    dry_run: bool = True


def _lang(value: str) -> str:
    return value if value in SUPPORTED_LANGUAGES else "de"


def _t(lang: str, key: str) -> str:
    return TRANSLATIONS[_lang(lang)][key]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_contract_dates(
    start_raw: str | None, end_raw: str | None, max_end_raw: str | None, ai_controls_end_date: bool
) -> tuple[str, str | None, str | None]:
    today = datetime.now(UTC).date()
    default_start = today
    default_max_end = today + timedelta(days=30)

    try:
        start_date = date.fromisoformat(start_raw) if start_raw else default_start
        max_end_date = date.fromisoformat(max_end_raw) if max_end_raw else None
        end_date = date.fromisoformat(end_raw) if end_raw else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc

    if max_end_date is None and not ai_controls_end_date:
        max_end_date = default_max_end

    if max_end_date is not None and max_end_date < start_date:
        raise HTTPException(status_code=400, detail="contract_max_end_date must be on or after contract_start_date.")
    if end_date is not None:
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="contract_end_date must be on or after contract_start_date.")
        if max_end_date is not None and end_date > max_end_date:
            raise HTTPException(status_code=400, detail="contract_end_date must not be after contract_max_end_date.")
    return (
        start_date.isoformat(),
        (end_date.isoformat() if end_date else None),
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
    taboo_text = answers.get("q7_taboo_text", "")
    open_context = answers.get("q9_open_context", "")
    safety_mode = str(answers.get("q10_safety_mode", "safeword"))
    safety_profile: dict[str, str | dict[str, str]] = {"mode": safety_mode}
    if safety_mode == "safeword":
        safeword = str(answers.get("q10_safeword", "")).strip()
        if safeword:
            safety_profile["safeword"] = safeword
    elif safety_mode == "traffic_light":
        safety_profile["traffic_light_words"] = {"green": "green", "yellow": "yellow", "red": "red"}

    return {
        "psychogram_version": "2.4.0",
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
        "created_at": now,
        "updated_at": now,
    }


def _get_db_session(request: Request):
    return request.app.state.db_session_factory()


def _require_user_token(user_id: str, auth_token: str, db) -> User:
    token_user_id = auth_tokens.get(auth_token)
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
        db_session = db.get(ChastitySession, session_id)
        if db_session is None:
            return False
        db_session.psychogram_snapshot_json = json.dumps(setup_session["psychogram"])
        db_session.policy_snapshot_json = json.dumps(setup_session["policy_preview"])
        db_session.updated_at = datetime.now(UTC)
        db.add(db_session)
        db.commit()
        return True
    finally:
        db.close()


def _build_ai_context_summary(psychogram: dict, policy: dict) -> str:
    traits = psychogram.get("traits", {})
    top_traits = ", ".join(
        f"{name}:{score}"
        for name, score in sorted(traits.items(), key=lambda item: item[1], reverse=True)[:4]
    )
    interaction = psychogram.get("interaction_preferences", {})
    safety = psychogram.get("safety_profile", {})
    personal = psychogram.get("personal_preferences", {})
    limits = (policy or {}).get("limits", {})
    interaction_policy = (policy or {}).get("interaction_profile", {})

    safety_mode = safety.get("mode", "safeword")
    safety_text = f"mode={safety_mode}"
    if safety_mode == "safeword" and safety.get("safeword"):
        safety_text = f"{safety_text}, safeword={safety.get('safeword')}"
    if safety_mode == "traffic_light" and isinstance(safety.get("traffic_light_words"), dict):
        tl = safety.get("traffic_light_words")
        safety_text = f"{safety_text}, tl={tl.get('green','')}/{tl.get('yellow','')}/{tl.get('red','')}"

    return (
        f"summary={psychogram.get('summary', 'n/a')}; "
        f"top_traits={top_traits or 'n/a'}; "
        f"instruction_style={interaction.get('instruction_style', 'mixed')}; "
        f"escalation_mode={interaction.get('escalation_mode', 'moderate')}; "
        f"experience={interaction.get('experience_level', 5)}/"
        f"{interaction.get('experience_profile', 'intermediate')}; "
        f"grooming_preference={personal.get('grooming_preference', 'no_preference')}; "
        f"safety={safety_text}; "
        f"tone={interaction_policy.get('preferred_tone', 'balanced')}; "
        f"intensity={limits.get('max_intensity_level', 2)}; "
        f"hard_stop={policy.get('hard_stop_enabled', True)}"
    )


@api_router.post("/auth/register")
def register(payload: RegisterRequest, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        email = _normalize_email(payload.email)
        display_name = username
        existing_email = db.scalar(select(User).where(User.email == email))
        if existing_email is not None:
            raise HTTPException(status_code=409, detail="Email already registered.")
        existing_username = db.scalar(select(User).where(func.lower(User.display_name) == username.lower()))
        if existing_username is not None:
            raise HTTPException(status_code=409, detail="Username already registered.")

        user = User(
            id=str(uuid4()),
            email=email,
            display_name=display_name,
            password_hash=_hash_password(payload.password),
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()

        token = secrets.token_urlsafe(24)
        auth_tokens[token] = user.id
        store = load_sessions()
        draft_id, draft_session = _find_user_setup_session(store, user.id, {"draft", "setup_in_progress"})
        if draft_session is None:
            draft_session = _create_draft_setup_session(user.id, "de")
            draft_id = draft_session["setup_session_id"]
            store[draft_id] = draft_session
            save_sessions(store)
        return {
            "user_id": user.id,
            "username": username,
            "email": user.email,
            "display_name": user.display_name,
            "auth_token": token,
            "setup_session_id": draft_id,
            "setup_status": draft_session["status"],
        }
    finally:
        db.close()


@api_router.post("/auth/login")
def login(payload: LoginRequest, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        user = db.scalar(select(User).where(func.lower(User.display_name) == username.lower()))
        if user is None or not _verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        token = secrets.token_urlsafe(24)
        auth_tokens[token] = user.id
        store = load_sessions()
        draft_id, draft_session = _find_user_setup_session(store, user.id, {"draft", "setup_in_progress"})
        if draft_session is None:
            draft_session = _create_draft_setup_session(user.id, "de")
            draft_id = draft_session["setup_session_id"]
            store[draft_id] = draft_session
            save_sessions(store)
        return {
            "user_id": user.id,
            "username": user.display_name,
            "email": user.email,
            "display_name": user.display_name,
            "auth_token": token,
            "setup_session_id": draft_id,
            "setup_status": draft_session["status"],
        }
    finally:
        db.close()


@api_router.get("/auth/me")
def auth_me(auth_token: str, request: Request) -> dict:
    user_id = auth_tokens.get(auth_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token.")

    db = _get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid auth token.")
        return {"user_id": user.id, "email": user.email, "display_name": user.display_name}
    finally:
        db.close()


@api_router.get("/llm/profile")
def get_llm_profile(user_id: str, auth_token: str, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        _require_user_token(user_id, auth_token, db)
        profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == user_id))
        if profile is None:
            return {"configured": False}
        return {"configured": True, "profile": _serialize_llm_profile(profile)}
    finally:
        db.close()


@api_router.post("/llm/profile")
def upsert_llm_profile(payload: LLMProfileUpsertRequest, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        _require_user_token(payload.user_id, payload.auth_token, db)
        profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == payload.user_id))
        now = datetime.now(UTC)
        encrypted_key = (
            encrypt_secret(payload.api_key, request.app.state.config.SECRET_KEY)
            if payload.api_key and payload.api_key.strip()
            else None
        )

        if profile is None:
            if not encrypted_key:
                raise HTTPException(status_code=400, detail="api_key is required for first profile creation.")
            profile = LLMProfile(
                id=str(uuid4()),
                user_id=payload.user_id,
                provider_name=payload.provider_name.strip(),
                api_url=payload.api_url.strip(),
                api_key_encrypted=encrypted_key,
                chat_model=payload.chat_model.strip(),
                vision_model=(payload.vision_model.strip() if payload.vision_model else None),
                behavior_prompt=payload.behavior_prompt,
                is_active=payload.is_active,
                created_at=now,
                updated_at=now,
            )
            db.add(profile)
        else:
            profile.provider_name = payload.provider_name.strip()
            profile.api_url = payload.api_url.strip()
            if encrypted_key:
                profile.api_key_encrypted = encrypted_key
            profile.chat_model = payload.chat_model.strip()
            profile.vision_model = payload.vision_model.strip() if payload.vision_model else None
            profile.behavior_prompt = payload.behavior_prompt
            profile.is_active = payload.is_active
            profile.updated_at = now
            db.add(profile)
        db.commit()
        return {"configured": True, "profile": _serialize_llm_profile(profile)}
    finally:
        db.close()


@api_router.post("/llm/test")
def test_llm_profile(payload: LLMProfileTestRequest, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        _require_user_token(payload.user_id, payload.auth_token, db)
        profile = db.scalar(select(LLMProfile).where(LLMProfile.user_id == payload.user_id))
        if profile is None:
            raise HTTPException(status_code=404, detail="LLM profile not configured.")
        if not profile.is_active:
            raise HTTPException(status_code=400, detail="LLM profile is disabled.")

        if payload.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "profile": {
                    "provider_name": profile.provider_name,
                    "api_url": profile.api_url,
                    "chat_model": profile.chat_model,
                    "vision_model": profile.vision_model,
                    "has_api_key": bool(profile.api_key_encrypted),
                },
            }

        api_key = decrypt_secret(profile.api_key_encrypted, request.app.state.config.SECRET_KEY)
        ai_service = request.app.state.ai_service
        context = StoryTurnContext(
            session_id="llm-connectivity-test",
            action="Ping test action",
            language="en",
            psychogram_summary="test profile",
        )
        if hasattr(ai_service, "generate_narration_with_profile"):
            narration = ai_service.generate_narration_with_profile(
                context,
                api_url=profile.api_url,
                api_key=api_key,
                chat_model=profile.chat_model,
                behavior_prompt=profile.behavior_prompt,
            )
        else:
            narration = ai_service.generate_narration(context)

        return {"ok": True, "dry_run": False, "sample_response": narration}
    finally:
        db.close()


@api_router.post("/users")
def create_user(payload: UserCreateRequest, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        existing = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
        if existing is not None:
            return {
                "user_id": existing.id,
                "email": existing.email,
                "display_name": existing.display_name,
                "created": False,
            }

        user = User(
            id=str(uuid4()),
            email=payload.email.strip().lower(),
            display_name=payload.display_name.strip(),
            password_hash="legacy_no_login",
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "created": True,
        }
    finally:
        db.close()


@api_router.get("/users/{user_id}")
def get_user(user_id: str, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        characters = db.scalars(select(Character).where(Character.user_id == user_id)).all()
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat(),
            "characters": [
                {
                    "character_id": c.id,
                    "name": c.name,
                    "strength": c.strength,
                    "intelligence": c.intelligence,
                    "charisma": c.charisma,
                    "hp": c.hp,
                }
                for c in characters
            ],
        }
    finally:
        db.close()


@api_router.post("/users/{user_id}/characters")
def create_character(user_id: str, payload: CharacterCreateRequest, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        character = Character(
            id=str(uuid4()),
            user_id=user_id,
            name=payload.name.strip(),
            strength=payload.strength,
            intelligence=payload.intelligence,
            charisma=payload.charisma,
            hp=payload.hp,
            created_at=datetime.now(UTC),
        )
        db.add(character)
        db.commit()
        return {
            "character_id": character.id,
            "user_id": user_id,
            "name": character.name,
            "strength": character.strength,
            "intelligence": character.intelligence,
            "charisma": character.charisma,
            "hp": character.hp,
        }
    finally:
        db.close()


@api_router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "chastease-api"}


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
        api_key = decrypt_secret(profile.api_key_encrypted, request.app.state.config.SECRET_KEY)
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
        api_key = decrypt_secret(profile.api_key_encrypted, request.app.state.config.SECRET_KEY)
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
    psychogram = setup_session.get("psychogram") or {}
    policy = setup_session.get("policy_preview") or {}
    lang = _lang(setup_session.get("language", "de"))
    action = (
        "Analyze this psychogram for dashboard summary. Provide concise guidance: tone, boundaries, intensity and first steps."
        if lang == "en"
        else "Analysiere dieses Psychogramm für eine Dashboard-Zusammenfassung. Gib kurze Hinweise zu Ton, Grenzen, Intensität und ersten Schritten."
    )
    try:
        return _generate_ai_narration_for_setup_preview(
            db,
            request,
            setup_session["user_id"],
            action,
            lang,
            psychogram,
            policy,
        )
    except Exception:
        interaction = psychogram.get("interaction_preferences", {})
        safety = psychogram.get("safety_profile", {})
        return (
            f"Profilanalyse: escalation={interaction.get('escalation_mode', 'moderate')}, "
            f"experience={interaction.get('experience_profile', 'intermediate')}, "
            f"safety={safety.get('mode', 'safeword')}."
        )


@api_router.post("/story/turn")
def story_turn(payload: StoryTurnRequest, request: Request) -> dict:
    lang = _lang(payload.language)
    action = payload.action.strip()
    if not action:
        raise HTTPException(status_code=400, detail=_t(lang, "action_required"))
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="Field 'session_id' is required.")

    db = _get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        narration = _generate_ai_narration_for_session(db, request, session, action, lang)

        current_turn_no = db.scalar(
            select(func.max(Turn.turn_no)).where(Turn.session_id == session.id)
        )
        next_turn_no = (current_turn_no or 0) + 1

        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=action,
            ai_narration=narration,
            language=lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
        "next_state": "awaiting_wearer_action",
    }


@api_router.post("/setup/sessions/{setup_session_id}/chat-preview")
def setup_chat_preview(setup_session_id: str, payload: SetupChatPreviewRequest, request: Request) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    if setup_session["user_id"] != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid user for setup session.")
    token_user_id = auth_tokens.get(payload.auth_token)
    if token_user_id != payload.user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")
    if setup_session.get("psychogram") is None or setup_session.get("policy_preview") is None:
        raise HTTPException(status_code=400, detail="Submit questionnaire answers before chat preview.")

    lang = _lang(payload.language)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")
    action_text = message

    db = _get_db_session(request)
    try:
        narration_raw = _generate_ai_narration_for_setup_preview(
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
    narration, pending_actions, generated_files = _extract_pending_actions(narration_raw)
    return {
        "result": "accepted_preview",
        "setup_session_id": setup_session_id,
        "narration": narration,
        "pending_actions": pending_actions,
        "generated_files": generated_files,
        "preview": True,
        "next_state": "awaiting_wearer_action",
    }


@api_router.post("/chat/turn")
def chat_turn(payload: ChatTurnRequest, request: Request) -> dict:
    lang = _lang(payload.language)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")

    action_text = message

    db = _get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")

        narration_raw = _generate_ai_narration_for_session(
            db, request, session, action_text, lang, payload.attachments
        )
        narration, pending_actions, generated_files = _extract_pending_actions(narration_raw)

        current_turn_no = db.scalar(
            select(func.max(Turn.turn_no)).where(Turn.session_id == session.id)
        )
        next_turn_no = (current_turn_no or 0) + 1
        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=action_text,
            ai_narration=narration,
            language=lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
        "pending_actions": pending_actions,
        "generated_files": generated_files,
        "next_state": "awaiting_wearer_action",
    }


@api_router.post("/chat/vision-review")
def chat_vision_review(payload: ChatVisionReviewRequest, request: Request) -> dict:
    lang = _lang(payload.language)
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

    db = _get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        narration_raw = _generate_ai_narration_for_session(db, request, session, prompt, lang, attachments)
        narration, pending_actions, generated_files = _extract_pending_actions(narration_raw)

        current_turn_no = db.scalar(select(func.max(Turn.turn_no)).where(Turn.session_id == session.id))
        next_turn_no = (current_turn_no or 0) + 1
        turn = Turn(
            id=str(uuid4()),
            session_id=session.id,
            turn_no=next_turn_no,
            player_action=f"{prompt} [image:{payload.picture_name or 'upload'}]",
            ai_narration=narration,
            language=lang,
            created_at=datetime.now(UTC),
        )
        session.updated_at = datetime.now(UTC)
        db.add(turn)
        db.add(session)
        db.commit()
    finally:
        db.close()

    return {
        "result": "accepted",
        "session_id": payload.session_id,
        "turn_no": next_turn_no,
        "narration": narration,
        "pending_actions": pending_actions,
        "generated_files": generated_files,
        "next_state": "awaiting_wearer_action",
    }


@api_router.post("/chat/actions/execute")
def chat_action_execute(payload: ChatActionExecuteRequest, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        session = db.get(ChastitySession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        session.updated_at = datetime.now(UTC)
        db.add(session)
        db.commit()
    finally:
        db.close()
    return {
        "executed": True,
        "session_id": payload.session_id,
        "action_type": payload.action_type,
        "payload": payload.payload,
        "message": "Action execution placeholder completed.",
    }


@api_router.post("/setup/sessions")
def start_setup_session(payload: SetupStartRequest, request: Request) -> dict:
    now = _now_iso()
    lang = _lang(payload.language)
    contract_start_date, contract_end_date, contract_max_end_date = _resolve_contract_dates(
        payload.contract_start_date,
        payload.contract_end_date,
        payload.contract_max_end_date,
        payload.ai_controls_end_date,
    )
    opening_limit_period = payload.opening_limit_period
    max_openings_in_period = payload.max_openings_in_period
    if payload.max_openings_per_day is not None:
        opening_limit_period = "day"
        max_openings_in_period = payload.max_openings_per_day
    db = _get_db_session(request)
    try:
        token_user_id = auth_tokens.get(payload.auth_token)
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


@api_router.post("/setup/sessions/{setup_session_id}/answers")
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
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)
    applied_to_active_session = _sync_setup_snapshot_to_active_session(request, setup_session)

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


@api_router.get("/setup/sessions/{setup_session_id}")
def get_setup_session(setup_session_id: str) -> dict:
    return _get_session_or_404(setup_session_id)


@api_router.get("/sessions/active")
def get_active_chastity_session(user_id: str, auth_token: str, request: Request) -> dict:
    token_user_id = auth_tokens.get(auth_token)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = _get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        session = db.scalar(
            select(ChastitySession)
            .where(ChastitySession.user_id == user_id)
            .where(ChastitySession.status == "active")
            .order_by(ChastitySession.created_at.desc())
        )
        if session is None:
            return {"has_active_session": False}

        return {"has_active_session": True, "chastity_session": _serialize_chastity_session(session)}
    finally:
        db.close()


@api_router.delete("/sessions/active")
def kill_active_chastity_session(
    user_id: str, auth_token: str, request: Request, setup_session_id: str | None = None
) -> dict:
    if not getattr(request.app.state.config, "ENABLE_SESSION_KILL", False):
        raise HTTPException(status_code=404, detail="Not found.")

    token_user_id = auth_tokens.get(auth_token)
    if token_user_id != user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token for user.")

    db = _get_db_session(request)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        session = db.scalar(
            select(ChastitySession)
            .where(ChastitySession.user_id == user_id)
            .where(ChastitySession.status == "active")
            .order_by(ChastitySession.created_at.desc())
        )
        deleted = False
        killed_session_id = None
        if session is not None:
            turns = db.scalars(select(Turn).where(Turn.session_id == session.id)).all()
            for turn in turns:
                db.delete(turn)
            killed_session_id = session.id
            db.delete(session)
            deleted = True

        db.commit()

        deleted_setup_session = False
        if setup_session_id:
            store = load_sessions()
            setup_session = store.get(setup_session_id)
            if setup_session and setup_session.get("user_id") == user_id:
                del store[setup_session_id]
                save_sessions(store)
                deleted_setup_session = True

        store = load_sessions()
        draft_id, draft_session = _find_user_setup_session(store, user_id, {"draft", "setup_in_progress"})
        if draft_session is None:
            draft_session = _create_draft_setup_session(user_id, "de")
            draft_id = draft_session["setup_session_id"]
            store[draft_id] = draft_session
            save_sessions(store)

        if not deleted and not deleted_setup_session:
            return {
                "deleted": False,
                "reason": "no_active_or_setup_session",
                "setup_session_id": draft_id,
                "setup_status": draft_session["status"],
            }

        return {
            "deleted": deleted or deleted_setup_session,
            "killed_session_id": killed_session_id,
            "deleted_setup_session": deleted_setup_session,
            "setup_session_id": draft_id,
            "setup_status": draft_session["status"],
        }
    finally:
        db.close()


@api_router.get("/sessions/{session_id}")
def get_chastity_session(session_id: str, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        return _serialize_chastity_session(session)
    finally:
        db.close()


@api_router.get("/sessions/{session_id}/turns")
def get_session_turns(session_id: str, request: Request) -> dict:
    db = _get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        turns = db.scalars(select(Turn).where(Turn.session_id == session_id).order_by(Turn.turn_no)).all()
        return {
            "session_id": session_id,
            "turns": [
                {
                    "turn_no": turn.turn_no,
                    "player_action": turn.player_action,
                    "ai_narration": turn.ai_narration,
                    "language": turn.language,
                    "created_at": turn.created_at.isoformat(),
                }
                for turn in turns
            ],
        }
    finally:
        db.close()


@api_router.post("/setup/sessions/{setup_session_id}/complete")
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

    setup_session["status"] = "configured"
    setup_session["updated_at"] = _now_iso()
    session_id = str(uuid4())
    setup_session["active_session_id"] = session_id
    store[setup_session_id] = setup_session
    save_sessions(store)

    db = _get_db_session(request)
    try:
        psychogram_analysis = _generate_psychogram_analysis_for_setup(db, request, setup_session)
        setup_session["psychogram_analysis"] = psychogram_analysis
        setup_session["psychogram"]["analysis"] = psychogram_analysis

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
            "psychogram_brief": setup_session.get("psychogram_analysis")
            or _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
            "psychogram_analysis": setup_session.get("psychogram_analysis"),
        },
    }


@api_router.patch("/setup/sessions/{setup_session_id}/psychogram")
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
    applied_to_active_session = _sync_setup_snapshot_to_active_session(request, setup_session)

    return {
        "setup_session_id": setup_session_id,
        "message": _t(lang, "recalibration_done"),
        "psychogram": setup_session["psychogram"],
        "policy_preview": setup_session["policy_preview"],
        "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
        "applied_to_active_session": applied_to_active_session,
    }


@api_router.get("/setup/questionnaire")
def get_setup_questionnaire(language: Literal["de", "en"] = "de") -> dict:
    lang = _lang(language)
    return {
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "language": lang,
        "questions": _localized_questions(lang),
    }


@api_router.get("/setup/demo")
def setup_demo_redirect():
    return RedirectResponse(url="/app", status_code=307)
