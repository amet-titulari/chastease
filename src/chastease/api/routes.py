from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from chastease.repositories.setup_store import load_sessions, save_sessions

api_router = APIRouter()

QUESTIONNAIRE_VERSION = "setup-q-v2.1"
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
        "type": "scale_10",
        "texts": {
            "de": "Wie wichtig sind dir klare, schriftliche Regeln und genau definierte Erwartungen?",
            "en": "How important are clear written rules and well-defined expectations to you?",
        },
        "weights": {"structure_need": 1.0, "protocol_affinity": 0.4},
    },
    {
        "id": "q2_strictness_authority",
        "type": "scale_10",
        "texts": {
            "de": "Wie stark moechtest du in dieser Session Strenge, Konsequenz und Autoritaet erleben?",
            "en": "How strongly do you want to experience strictness, consequences, and authority in this session?",
        },
        "weights": {"strictness_affinity": 1.0, "accountability_need": 0.3},
    },
    {
        "id": "q3_control_need",
        "type": "scale_10",
        "texts": {
            "de": "Wie sehr brauchst du das Gefuehl, wirklich kontrolliert und ueberwacht zu werden?",
            "en": "How much do you need to feel genuinely controlled and monitored?",
        },
        "weights": {"accountability_need": 1.0, "structure_need": 0.3},
    },
    {
        "id": "q4_praise_importance",
        "type": "scale_10",
        "texts": {
            "de": "Wie wichtig ist positives Feedback/Anerkennung fuer gutes Verhalten?",
            "en": "How important is positive feedback/recognition for good behavior?",
        },
        "weights": {"praise_affinity": 1.0},
    },
    {
        "id": "q5_novelty_challenge",
        "type": "scale_10",
        "texts": {
            "de": "Wie sehr suchst du Abwechslung, neue Aufgaben und ungewohnte Herausforderungen?",
            "en": "How much are you looking for variety, new tasks, and unfamiliar challenges?",
        },
        "weights": {"novelty_affinity": 0.7, "challenge_affinity": 0.7},
    },
    {
        "id": "q6_intensity_1_5",
        "type": "scale_5",
        "texts": {
            "de": "Welche Intensitaet passt aktuell am besten? (1=sanft ... 5=sehr fordernd)",
            "en": "What intensity fits best right now? (1=gentle ... 5=very demanding)",
        },
        "weights": {"strictness_affinity": 0.8, "challenge_affinity": 0.6},
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


class SetupStartRequest(BaseModel):
    wearer_id: str = Field(min_length=1)
    hard_stop_enabled: bool = True
    autonomy_mode: Literal["execute", "suggest"] = "execute"
    integrations: list[Literal["ttlock", "chaster", "emlalock"]] = Field(default_factory=list)
    language: Literal["de", "en"] = "de"
    blocked_trigger_words: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)


class SetupAnswer(BaseModel):
    question_id: str
    value: int | str


class SetupAnswersRequest(BaseModel):
    answers: list[SetupAnswer]


class PsychogramRecalibrationRequest(BaseModel):
    update_reason: str = Field(min_length=3)
    trait_overrides: dict[str, int] = Field(default_factory=dict)


def _lang(value: str) -> str:
    return value if value in SUPPORTED_LANGUAGES else "de"


def _t(lang: str, key: str) -> str:
    return TRANSLATIONS[_lang(lang)][key]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _localized_questions(language: str) -> list[dict]:
    lang = _lang(language)
    localized = []
    for question in QUESTION_BANK:
        item = {
            "question_id": question["id"],
            "text": question["texts"][lang],
            "type": question["type"],
        }
        if question["type"] == "scale_10":
            item["scale_min"] = 1
            item["scale_max"] = 10
            item["scale_hint"] = (
                "1=trifft nicht zu, 10=trifft sehr zu"
                if lang == "de"
                else "1=does not apply, 10=applies strongly"
            )
        elif question["type"] == "scale_5":
            item["scale_min"] = 1
            item["scale_max"] = 5
            item["scale_hint"] = (
                "1=sanft, 5=sehr fordernd" if lang == "de" else "1=gentle, 5=very demanding"
            )
        elif question["type"] == "choice":
            item["options"] = [{"value": opt["value"], "label": opt[lang]} for opt in question["options"]]
        localized.append(item)
    return localized


def _validate_answer(question: dict, raw_value: int | str) -> int | str:
    q_type = question["type"]
    if q_type == "scale_10":
        if not isinstance(raw_value, int) or raw_value < 1 or raw_value > 10:
            raise ValueError("Expected integer value in range 1..10")
        return raw_value
    if q_type == "scale_5":
        if not isinstance(raw_value, int) or raw_value < 1 or raw_value > 5:
            raise ValueError("Expected integer value in range 1..5")
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
    if question_type == "scale_10":
        return round(((value - 1) / 9) * 100)
    if question_type == "scale_5":
        return round(((value - 1) / 4) * 100)
    return 50


def _psychogram_brief(psychogram: dict, policy: dict) -> str:
    traits = psychogram["traits"]
    top_traits = sorted(traits.items(), key=lambda item: item[1], reverse=True)[:3]
    top_text = ", ".join([f"{name}:{score}" for name, score in top_traits])
    tone = policy["interaction_profile"]["preferred_tone"]
    intensity = policy["limits"]["max_intensity_level"]
    return f"Top traits -> {top_text}. Tone={tone}, intensity={intensity}, confidence={psychogram['confidence']}."


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
        if qid in question_map and question_map[qid]["type"] in {"scale_10", "scale_5"} and isinstance(value, int)
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
    taboo_text = answers.get("q7_taboo_text", "")
    open_context = answers.get("q9_open_context", "")

    return {
        "psychogram_version": "2.0.0",
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
    return {
        "applied": True,
        "reason": "low_confidence",
        "tone": "balanced",
        "max_intensity_level": 2,
        "autonomy_profile": "suggest_first",
        "autonomy_bias": 80,
        "max_penalty_per_day_minutes": 20,
        "max_penalty_per_week_minutes": 90,
        "hard_stop_enabled": setup_session["hard_stop_enabled"],
    }


def _build_policy(setup_session: dict, psychogram: dict) -> dict:
    traits = psychogram["traits"]
    autonomy_profile = psychogram["interaction_preferences"]["autonomy_profile"]
    autonomy_bias = psychogram["interaction_preferences"]["autonomy_bias"]
    low_confidence = psychogram["confidence"] < 0.5
    conservative = _conservative_policy_defaults(setup_session) if low_confidence else {"applied": False}
    default_limits = conservative if low_confidence else {}

    return {
        "policy_version": "1.1.0",
        "hard_stop_enabled": setup_session["hard_stop_enabled"],
        "autonomy_mode": setup_session["autonomy_mode"],
        "integrations": setup_session["integrations"],
        "limits": {
            "max_intensity_level": default_limits.get(
                "max_intensity_level", max(1, min(5, round(traits["strictness_affinity"] / 20)))
            ),
            "max_penalty_per_day_minutes": default_limits.get("max_penalty_per_day_minutes", 60),
            "max_penalty_per_week_minutes": default_limits.get("max_penalty_per_week_minutes", 240),
            "allowed_challenge_categories": _derive_allowed_categories(traits),
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


@api_router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "chastease-api"}


@api_router.post("/story/turn")
def story_turn(payload: StoryTurnRequest) -> dict:
    lang = _lang(payload.language)
    action = payload.action.strip()
    if not action:
        raise HTTPException(status_code=400, detail=_t(lang, "action_required"))
    return {
        "result": "accepted",
        "narration": f"{_t(lang, 'story_prefix')}: {action}",
        "next_state": "pending-ai-engine",
    }


@api_router.post("/setup/sessions")
def start_setup_session(payload: SetupStartRequest) -> dict:
    setup_session_id = str(uuid4())
    now = _now_iso()
    lang = _lang(payload.language)

    store = load_sessions()
    store[setup_session_id] = {
        "setup_session_id": setup_session_id,
        "wearer_id": payload.wearer_id,
        "status": "setup_in_progress",
        "hard_stop_enabled": payload.hard_stop_enabled,
        "autonomy_mode": payload.autonomy_mode,
        "integrations": payload.integrations,
        "language": lang,
        "blocked_trigger_words": payload.blocked_trigger_words,
        "forbidden_topics": payload.forbidden_topics,
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "answers": [],
        "psychogram": None,
        "policy_preview": None,
        "created_at": now,
        "updated_at": now,
    }
    save_sessions(store)

    return {
        "setup_session_id": setup_session_id,
        "status": "setup_in_progress",
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "language": lang,
        "questions": _localized_questions(lang),
    }


@api_router.post("/setup/sessions/{setup_session_id}/answers")
def submit_setup_answers(setup_session_id: str, payload: SetupAnswersRequest) -> dict:
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

    setup_session["answers"] = [
        {"question_id": question_id, "value": value}
        for question_id, value in answers_by_question.items()
    ]
    setup_session["psychogram"] = _build_psychogram(setup_session)
    setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])
    setup_session["updated_at"] = _now_iso()
    store[setup_session_id] = setup_session
    save_sessions(store)

    return {
        "setup_session_id": setup_session_id,
        "status": setup_session["status"],
        "answered_questions": len(setup_session["answers"]),
        "total_questions": len(QUESTION_IDS),
        "psychogram_preview": setup_session["psychogram"],
        "policy_preview": setup_session["policy_preview"],
        "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
    }


@api_router.get("/setup/sessions/{setup_session_id}")
def get_setup_session(setup_session_id: str) -> dict:
    return _get_session_or_404(setup_session_id)


@api_router.post("/setup/sessions/{setup_session_id}/complete")
def complete_setup_session(setup_session_id: str) -> dict:
    store = load_sessions()
    setup_session = store.get(setup_session_id)
    if setup_session is None:
        raise HTTPException(status_code=404, detail=_t("de", "not_found"))
    lang = _lang(setup_session["language"])
    if setup_session["status"] != "setup_in_progress":
        raise HTTPException(status_code=409, detail=_t(lang, "cannot_complete"))
    if len(setup_session["answers"]) < 6:
        raise HTTPException(status_code=400, detail=_t(lang, "not_enough_answers"))

    if setup_session["psychogram"] is None:
        setup_session["psychogram"] = _build_psychogram(setup_session)
    if setup_session["policy_preview"] is None:
        setup_session["policy_preview"] = _build_policy(setup_session, setup_session["psychogram"])

    setup_session["status"] = "configured"
    setup_session["updated_at"] = _now_iso()
    session_id = str(uuid4())
    store[setup_session_id] = setup_session
    save_sessions(store)

    return {
        "setup_session_id": setup_session_id,
        "status": "configured",
        "chastity_session": {
            "session_id": session_id,
            "wearer_id": setup_session["wearer_id"],
            "status": "active",
            "policy": setup_session["policy_preview"],
            "psychogram": setup_session["psychogram"],
            "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
        },
    }


@api_router.patch("/setup/sessions/{setup_session_id}/psychogram")
def recalibrate_psychogram(setup_session_id: str, payload: PsychogramRecalibrationRequest) -> dict:
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

    return {
        "setup_session_id": setup_session_id,
        "message": _t(lang, "recalibration_done"),
        "psychogram": setup_session["psychogram"],
        "policy_preview": setup_session["policy_preview"],
        "psychogram_brief": _psychogram_brief(setup_session["psychogram"], setup_session["policy_preview"]),
    }


@api_router.get("/setup/questionnaire")
def get_setup_questionnaire(language: Literal["de", "en"] = "de") -> dict:
    lang = _lang(language)
    return {
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "language": lang,
        "questions": _localized_questions(lang),
    }


@api_router.get("/setup/demo", response_class=HTMLResponse)
def setup_demo() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chastease Setup Demo</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; margin: 0; background: #0b1220; color: #e8eefc; }
    .wrap { max-width: 1024px; margin: 0 auto; padding: 24px; }
    .card { background: #101a30; border: 1px solid #22314f; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    h1, h2 { margin: 0 0 10px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
    .qgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }
    label { display: block; font-size: 13px; color: #a9b9da; margin-bottom: 4px; }
    input, select, button, textarea { border-radius: 8px; border: 1px solid #2b3d63; background: #0f1930; color: #e8eefc; padding: 8px 10px; }
    input[type=range] { width: 100%; padding: 0; }
    button { background: #2d8cff; border: 0; cursor: pointer; }
    button:hover { background: #4aa0ff; }
    textarea { width: 100%; min-height: 280px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .small { font-size: 12px; color: #9ab0d8; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Setup Prototype Demo</h1>
    <p class="small">Try German/English setup and psychogram generation.</p>

    <div class="card">
      <h2>1) Start Setup Session</h2>
      <div class="row">
        <div><label>Wearer ID</label><input id="wearerId" value="wearer-demo" /></div>
        <div><label>Autonomy Mode</label><select id="autonomy"><option value="execute">execute</option><option value="suggest">suggest</option></select></div>
        <div><label>Language</label><select id="language"><option value="de">Deutsch</option><option value="en">English</option></select></div>
        <div><label>Hard Stop</label><select id="hardStop"><option value="true">enabled</option><option value="false">disabled</option></select></div>
      </div>
      <button onclick="startSetup()">Start Setup</button>
      <p id="setupSessionInfo" class="small"></p>
    </div>

    <div class="card">
      <h2>2) Answer Questionnaire</h2>
      <p class="small">Scale 1-10. Questions load based on selected language.</p>
      <div id="questionGrid" class="qgrid"></div>
      <button onclick="submitAnswers()">Submit Answers</button>
    </div>

    <div class="card">
      <h2>3) Complete Setup</h2>
      <button onclick="completeSetup()">Complete Setup</button>
    </div>

    <div class="card">
      <h2>Psychogram Brief</h2>
      <p id="brief" class="small">No evaluation yet.</p>
    </div>

    <div class="card">
      <h2>Response</h2>
      <textarea id="output" readonly></textarea>
    </div>
  </div>

  <script>
    let setupSessionId = null;
    let questions = [];

    function setOutput(data) {
      document.getElementById("output").value = JSON.stringify(data, null, 2);
      if (data.psychogram_brief) {
        document.getElementById("brief").textContent = data.psychogram_brief;
      }
    }

    function renderQuestions() {
      const grid = document.getElementById("questionGrid");
      grid.innerHTML = "";
      questions.forEach((q) => {
        const wrap = document.createElement("div");
        if (q.type === "scale_10" || q.type === "scale_5") {
          const mid = q.type === "scale_5" ? 3 : 5;
          wrap.innerHTML = `
            <label>${q.text} (${q.question_id})</label>
            <input id="q_${q.question_id}" type="range" min="${q.scale_min}" max="${q.scale_max}" step="1" value="${mid}" oninput="document.getElementById('v_${q.question_id}').textContent=this.value" />
            <div class="small"><span>${q.scale_hint || ""}</span></div>
            <div class="small">Wert: <strong id="v_${q.question_id}">${mid}</strong></div>
          `;
        } else if (q.type === "choice") {
          const options = (q.options || []).map((o) => `<option value="${o.value}">${o.label}</option>`).join("");
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label><select id="q_${q.question_id}">${options}</select>`;
        } else {
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label><textarea id="q_${q.question_id}" rows="3" style="min-height:72px;"></textarea>`;
        }
        grid.appendChild(wrap);
      });
    }

    async function startSetup() {
      const payload = {
        wearer_id: document.getElementById("wearerId").value,
        autonomy_mode: document.getElementById("autonomy").value,
        hard_stop_enabled: document.getElementById("hardStop").value === "true",
        language: document.getElementById("language").value,
        integrations: ["ttlock"]
      };
      const res = await fetch("/api/v1/setup/sessions", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.setup_session_id) {
        setupSessionId = data.setup_session_id;
        questions = data.questions || [];
        renderQuestions();
        document.getElementById("setupSessionInfo").textContent = "setup_session_id: " + setupSessionId;
      }
      setOutput(data);
    }

    async function submitAnswers() {
      if (!setupSessionId) return setOutput({error: "Start setup first."});
      const answers = questions.map((q) => ({
        question_id: q.question_id,
        value:
          q.type === "scale_10" || q.type === "scale_5"
            ? Number(document.getElementById(`q_${q.question_id}`).value)
            : document.getElementById(`q_${q.question_id}`).value,
      }));
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/answers`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({answers})
      });
      const data = await res.json();
      setOutput(data);
    }

    async function completeSetup() {
      if (!setupSessionId) return setOutput({error: "Start setup first."});
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/complete`, { method: "POST" });
      const data = await res.json();
      setOutput(data);
    }
  </script>
</body>
</html>
"""
