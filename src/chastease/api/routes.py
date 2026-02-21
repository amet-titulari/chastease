from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from chastease.repositories.setup_store import load_sessions, save_sessions

api_router = APIRouter()

QUESTIONNAIRE_VERSION = "setup-q-v2"
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
    },
}

# Inspired by psychometric preference tests; intentionally authored, not copied.
QUESTION_BANK = [
    {
        "id": "q_rule_structure",
        "texts": {
            "de": "Klare Regeln geben mir Sicherheit und Fokus.",
            "en": "Clear rules give me safety and focus.",
        },
        "weights": {"structure_need": 1.0, "protocol_affinity": 0.4},
    },
    {
        "id": "q_strict_guidance",
        "texts": {
            "de": "Ich bevorzuge eine eher strenge Fuehrung.",
            "en": "I prefer rather strict guidance.",
        },
        "weights": {"strictness_affinity": 1.0, "accountability_need": 0.3},
    },
    {
        "id": "q_positive_reinforcement",
        "texts": {
            "de": "Positive Bestaerkung motiviert mich stark.",
            "en": "Positive reinforcement motivates me strongly.",
        },
        "weights": {"praise_affinity": 1.0},
    },
    {
        "id": "q_control_checkins",
        "texts": {
            "de": "Regelmaessige Kontroll-Check-ins helfen mir dranzubleiben.",
            "en": "Regular accountability check-ins help me stay consistent.",
        },
        "weights": {"accountability_need": 1.0, "structure_need": 0.3},
    },
    {
        "id": "q_challenge_tasks",
        "texts": {
            "de": "Ich mag herausfordernde Aufgaben und Meilensteine.",
            "en": "I enjoy challenging tasks and milestones.",
        },
        "weights": {"challenge_affinity": 1.0},
    },
    {
        "id": "q_variety",
        "texts": {
            "de": "Abwechslung haelt meine Motivation hoch.",
            "en": "Variety keeps my motivation high.",
        },
        "weights": {"novelty_affinity": 1.0},
    },
    {
        "id": "q_service_orientation",
        "texts": {
            "de": "Ich finde Erfuellen klarer Erwartungen besonders reizvoll.",
            "en": "I find fulfilling clear expectations especially rewarding.",
        },
        "weights": {"service_orientation": 1.0, "protocol_affinity": 0.3},
    },
    {
        "id": "q_protocol",
        "texts": {
            "de": "Rituale und feste Ablaeufe passen gut zu mir.",
            "en": "Rituals and fixed routines suit me well.",
        },
        "weights": {"protocol_affinity": 1.0, "structure_need": 0.4},
    },
    {
        "id": "q_direct_feedback",
        "texts": {
            "de": "Direktes Feedback ist fuer mich hilfreicher als Zurueckhaltung.",
            "en": "Direct feedback is more helpful to me than restraint.",
        },
        "weights": {"strictness_affinity": 0.5, "accountability_need": 0.5},
    },
    {
        "id": "q_balanced_care",
        "texts": {
            "de": "Ich mag einen Stil, der klare Führung mit Fuersorge verbindet.",
            "en": "I like a style that combines clear leadership with care.",
        },
        "weights": {"praise_affinity": 0.5, "strictness_affinity": 0.5},
    },
    {
        "id": "q_goal_tracking",
        "texts": {
            "de": "Messbare Ziele und Tracking helfen mir, motiviert zu bleiben.",
            "en": "Measurable goals and tracking help me stay motivated.",
        },
        "weights": {"accountability_need": 0.7, "structure_need": 0.3},
    },
    {
        "id": "q_adaptive_play",
        "texts": {
            "de": "Ich mag es, wenn der Verlauf kreativ und situativ angepasst wird.",
            "en": "I like it when the flow adapts creatively to the situation.",
        },
        "weights": {"novelty_affinity": 0.7, "challenge_affinity": 0.3},
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


class SetupAnswer(BaseModel):
    question_id: str
    value: int = Field(ge=1, le=10)


class SetupAnswersRequest(BaseModel):
    answers: list[SetupAnswer]


def _lang(value: str) -> str:
    return value if value in SUPPORTED_LANGUAGES else "de"


def _t(lang: str, key: str) -> str:
    return TRANSLATIONS[_lang(lang)][key]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _localized_questions(language: str) -> list[dict]:
    lang = _lang(language)
    return [
        {
            "question_id": question["id"],
            "text": question["texts"][lang],
            "scale_min": 1,
            "scale_max": 10,
            "scale_hint": "1=trifft nicht zu, 10=trifft sehr zu",
        }
        for question in QUESTION_BANK
    ]


def _build_psychogram(setup_session: dict) -> dict:
    lang = _lang(setup_session["language"])
    answers = {entry["question_id"]: entry["value"] for entry in setup_session["answers"]}
    weighted_sum = {key: 0.0 for key in TRAIT_KEYS}
    total_weight = {key: 0.0 for key in TRAIT_KEYS}

    for question in QUESTION_BANK:
        answer_value = answers.get(question["id"])
        if answer_value is None:
            continue
        normalized_answer = round(((answer_value - 1) / 9) * 100)
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
    confidence = round(0.5 + (len(answers) / len(QUESTION_IDS)) * 0.5, 2)
    summary = _t(lang, "summary_template").format(
        structure=traits["structure_need"],
        strictness=traits["strictness_affinity"],
        accountability=traits["accountability_need"],
    )

    return {
        "psychogram_version": "2.0.0",
        "source_questionnaire_version": QUESTIONNAIRE_VERSION,
        "source_model": "bdsmtest-inspired",
        "created_at": _now_iso(),
        "traits": traits,
        "likes": likes,
        "dislikes": dislikes,
        "summary": summary,
        "confidence": confidence,
    }


def _build_policy(setup_session: dict, psychogram: dict) -> dict:
    traits = psychogram["traits"]
    return {
        "policy_version": "1.1.0",
        "hard_stop_enabled": setup_session["hard_stop_enabled"],
        "autonomy_mode": setup_session["autonomy_mode"],
        "integrations": setup_session["integrations"],
        "limits": {
            "max_intensity_level": max(1, min(5, round(traits["strictness_affinity"] / 20))),
            "max_penalty_per_day_minutes": 60,
            "max_penalty_per_week_minutes": 240,
        },
        "interaction_profile": {
            "preferred_tone": "strict" if traits["strictness_affinity"] >= 70 else "balanced",
            "control_frequency_hint": "high" if traits["accountability_need"] >= 70 else "medium",
            "novelty_hint": "high" if traits["novelty_affinity"] >= 70 else "medium",
        },
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
    for answer in payload.answers:
        if answer.question_id not in known_ids:
            raise HTTPException(status_code=400, detail=f"{_t(lang, 'unknown_question')}: {answer.question_id}")

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
        },
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
      <h2>Response</h2>
      <textarea id="output" readonly></textarea>
    </div>
  </div>

  <script>
    let setupSessionId = null;
    let questions = [];

    function setOutput(data) {
      document.getElementById("output").value = JSON.stringify(data, null, 2);
    }

    function renderQuestions() {
      const grid = document.getElementById("questionGrid");
      grid.innerHTML = "";
      questions.forEach((q) => {
        const wrap = document.createElement("div");
        wrap.innerHTML = `
          <label>${q.text} (${q.question_id})</label>
          <input id="q_${q.question_id}" type="range" min="1" max="10" step="1" value="5" oninput="document.getElementById('v_${q.question_id}').textContent=this.value" />
          <div class="small">
            <span>trifft nicht zu</span>
            <span style="float:right;">trifft sehr zu</span>
          </div>
          <div class="small">Wert: <strong id="v_${q.question_id}">5</strong></div>
        `;
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
        value: Number(document.getElementById(`q_${q.question_id}`).value),
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
