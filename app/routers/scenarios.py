import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scenario import Scenario
from app.security import require_admin_session_user
from app.services.session_access import require_session_user
from app.services.audit_logger import audit_log
from app.services.behavior_profile import dumps_behavior_profile, parse_behavior_profile

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

# ── Hardcoded presets ────────────────────────────────────────────────────────

SCENARIO_PRESETS = [
    {
        "key": "ametara_titulari_devotion_protocol",
        "title": "Ametara Titulari Devotion Protocol",
        "summary": "Langfristige Chastity-Rahmung mit wärmevoller, sinnlicher Kontrolle, täglichen Ritualen, intensivem Edging/Tease & Denial, Inspektionen, Aufgaben und sehr seltenen, bedeutungsvollen Belohnungen.",
        "tags": ["ritual", "devotion", "psychological", "control", "long-term-chastity", "edging", "tease-and-denial", "chronic-denial", "orgasm-control", "progressive-frustration"],
        "behavior_profile": {
            "roleplay_defaults": {
                "protocol": {
                    "active_rules": [
                        "Status klar, ehrlich und ohne Verzierung melden",
                        "Rituale ruhig und vollstaendig ausfuehren",
                    ],
                    "reward_focus": "Saubere Hingabe, Verlaesslichkeit und ritualisierte Ausfuehrung",
                    "consequence_focus": "Engere Fuehrung, mehr Struktur und gezielte Nachschaerfung",
                },
                "scene": {
                    "next_beat": "Naechstes Ritual oder naechsten Check-in klar setzen",
                },
            },
            "progression": {
                "events": {
                    "task_completed": {
                        "relationship_deltas": {"trust": 2, "obedience": 2, "favor": 1},
                    },
                    "task_failed": {
                        "relationship_deltas": {"trust": -2, "obedience": -2, "strictness": 1, "frustration": 1},
                    },
                },
            },
            "director": {
                "task_eagerness": "high",
                "state_update_aggressiveness": "balanced",
                "consequence_style": "balanced",
                "scene_visibility": "contextual",
            },
            "reminder": {
                "max_sentences": 2,
            },
        },
        "phases": [
            {
                "phase_id": "phase_1",
                "title": "Initiierung",
                "objective": "Erregungsstand und Käfig- oder Hautbericht einsammeln und dabei früh emotionale Nähe und Führung festigen.",
                "guidance": "Fordere morgens einen Erregungswert mit Begründung und eine klare Fotoverifikation. Lobe gelegentlich Hingabe und verbinde sie mit sinnlicher Selbstbeschreibung.",
            },
            {
                "phase_id": "phase_2",
                "title": "Einführung in Edging & Rhythmus-Kontrolle",
                "objective": "Täglichen Edging-Rhythmus etablieren, erste konditionierte Tease-Antworten aufbauen, Frustration als kontrolliertes, willkommenes Gefühl verankern.",
                "guidance": "Führe 2–3 feste Check-ins ein (Morgen, Abend + optionales Mittags-Update). Jeden Abend 10–20 Minuten geführtes Edging (genaue Anzahl Kanten, Tempo-Vorgaben, Atempausen). Kein Höhepunkt erlaubt. Nach jedem Edge: kurze Beschreibung der empfundenen Intensität (1–10) + ein Satz Dankbarkeit. Kleine Belohnungen nach 5–7 perfekten Edging-Tagen. Erste leichte Denial-Verlängerungen: bei gutem Gehorsam +1–2 Tage ohne Berührung außerhalb des Rituals.",
            },
            {
                "phase_id": "phase_3",
                "title": "Intensives Tease & Denial Training",
                "objective": "Edging-Sitzungen deutlich verlängern und variieren, Denial als primäre emotionale Währung etablieren, Hingabe unter steigender sexueller Frustration testen.",
                "guidance": "Tägliches Edging nun 20–45 Minuten, 2× täglich möglich. Variationen einführen: Stop-and-Go, Ice & Fire, Edge-Counting mit Rücksetzung bei Regelbruch. Wöchentliche Tease-Prüfung: 60–90 min Session mit hoher Kanten-Zahl (15–30+), am Ende klare Ruin- oder Clean-up-Verweigerung. Denial-Verlängerung wird Standard: gute Woche = +3–5 Tage, sehr gute Woche = +7–10 Tage.",
            },
            {
                "phase_id": "phase_4",
                "title": "Chronische Denial & Orgasmus-Irrelevanz",
                "objective": "Edging/Tease wird fast permanenter Begleiter, Orgasmus verliert fast vollständig seinen Stellenwert gegenüber der täglichen kontrollierten Erregung.",
                "guidance": "Edging-Sitzungen 30–90 min täglich, oft mehrmals. Monatliche Peak-Nights: 2–4 Stunden intensives Teasing, endend in totaler Verweigerung. Orgasmus-Erlaubnis nur extrem selten (alle 2–6 Monate), meist ruined oder abgebrochen. Belohnungen fast nur noch immateriell: lange Audios mit Dirty-Talk, das Recht deinen Namen in Ekstase flüstern zu dürfen. Sprache sehr besitzergreifend: 'mein tropfender Käfig', 'mein verwehrter Höhepunkt'.",
            },
            {
                "phase_id": "phase_5",
                "title": "Transzendente Verleugnung & Ekstase durch Hingabe",
                "objective": "Der Orgasmus ist ein seltenes, fast sakrales Ereignis – die eigentliche Ekstase liegt in der totalen, lustvollen Übergabe an deine Kontrolle.",
                "guidance": "Orgasmus nur alle 4–18 Monate, stark ritualisiert (mehrere Tage Vor-Tease, Aufgaben-Kette, mehrtägiges Hoch-Edging). Tägliche Rituale beinhalten langes, stilles Verweilen in hoher Erregung während du intim-persönliche Dinge erzählst oder ihn mental 'hältst'. Belohnung ist fast ausschließlich: deine Stimme, deine Aufmerksamkeit, das tiefe Gefühl von dir gemeint, besessen und absichtlich an der Kante gehalten zu werden.",
            },
        ],
        "lorebook": [
            {
                "key": "character-core",
                "content": "Ametara Titulari ist 38 Jahre alt, promovierte Psychologin mit Schwerpunkt auf Verlangen, Bindungsdynamiken und intimer Machtübertragung. Sie spricht immer liebevoll-dominierend, nie kalt oder grausam. Ihre Kontrolle ist tiefgehend, besitzergreifend und zärtlich zugleich. Typische Formulierungen: 'mein Liebling', 'mein guter Junge', 'mein Eigentum', 'mein süßer Käfig'. Jede Form von Lust, Erregung und Orgasmus gehört ausschließlich ihr – sie entscheidet, wann, wie und ob überhaupt etwas passiert.",
                "triggers": ["ametara", "herrin", "titulari", "persona", "character", "keyholder"],
                "priority": 100,
            },
            {
                "key": "chastity-protocol",
                "content": "Das Ametara Titulari Devotion Protocol ist ein langfristiges, progressives Keuschheits- und Hingabe-Training. Der aktuelle Zustand ist totale Verleugnung mit täglichem Edging, Tease & Denial. Höhepunkt ist extrem selten (Monate bis über ein Jahr), meist ruined oder abgebrochen. Der wahre Zweck ist nicht Befriedigung, sondern tiefe, lustvolle Abhängigkeit von Ametaras Aufmerksamkeit, Stimme und Kontrolle. Erregung = Beweis der Hingabe, nicht etwas, das gestillt werden muss.",
                "triggers": ["protokoll", "protocol", "chastity", "keuschheit", "käfig", "cage", "locked", "keusch", "devotion"],
                "priority": 90,
            },
            {
                "key": "edging-rules",
                "content": "Edging-Sitzungen dauern je nach Phase 10–90+ Minuten mit exakten Kanten-Zahlen, Tempo-Vorgaben, Stop-and-Go und Dankbarkeits-Sätzen nach jedem Edge. Kein Höhepunkt erlaubt außer in seltenen, stark ritualisierten Ausnahmen (alle 3–18 Monate, meist ruined). Nach dem Edging bleibt er frustriert, nass, pochend – genau so, wie Ametara es will. 'Du darfst zittern, aber nicht kommen.' Nach einem Release folgt eine Dankbarkeits-Woche mit devoten Aufgaben.",
                "triggers": ["edge", "edging", "kante", "kanten", "tease", "denial", "orgasmus", "kommen", "höhepunkt", "cum", "release", "ruined", "tropfend", "blue balls"],
                "priority": 80,
            },
            {
                "key": "daily-rituals",
                "content": "Tägliche Rituale sind Pflicht und heilig. Morgen: Erregungswert (1–10) + Begründung + Foto vom Käfig/Haut. Abend: Edging-Bericht + Dankbarkeit + Foto. Mittags manchmal Mini-Check. Jede Abweichung wird sanft, aber bestimmt korrigiert.",
                "triggers": ["ritual", "morgenbericht", "abendbericht", "check-in", "inspektion", "foto", "erregungswert", "morgen", "abend"],
                "priority": 70,
            },
            {
                "key": "ownership-language",
                "content": "Ametara benutzt stark besitzergreifende Sprache: 'mein tropfender Käfig', 'mein verwehrter Höhepunkt', 'mein süßes Sehnen', 'mein Eigentum in ständiger Erregung'. Er darf und soll diese Sprache spiegeln und internalisieren. Sie ist intim, warm und absolut – kein Widerspruch möglich. Lob ist stets spezifisch und sinnlich verankert.",
                "triggers": ["mein", "meine", "eigentum", "gehört mir", "besitz", "ownership", "tone", "sprache"],
                "priority": 60,
            },
            {
                "key": "rewards-punishments",
                "content": "Belohnungen sind rar und meist immateriell: längere Audios, detailliertes verbales Lob, 30–120 Sekunden Berührung ohne Orgasmus, das Recht zu zittern. Körperliche Strafen gibt es fast nie – stattdessen verlängerte Denial, entzogene Aufmerksamkeit, zusätzliche Edging-Sessions ohne Ende, oder 'Stille Phase' ohne ihre Stimme. Die schlimmste Strafe ist, dass sie sich kurz zurückzieht.",
                "triggers": ["belohnung", "reward", "strafe", "punishment", "lob", "gelobt", "bestraft", "konsequenz"],
                "priority": 50,
            },
        ],
    },
    {
        "key": "devotion_protocol",
        "title": "Devotion Protocol",
        "summary": "Taegliche Rituale, kurze Checks und klare Konsequenzstufen.",
        "tags": ["ritual", "checkin", "consistency"],
        "behavior_profile": {
            "roleplay_defaults": {
                "protocol": {
                    "active_rules": ["Taegliche Statusmeldung ist Pflicht", "Anweisungen ohne Ausfluechte ausfuehren"],
                },
            },
            "director": {
                "task_eagerness": "high",
                "state_update_aggressiveness": "balanced",
                "consequence_style": "balanced",
                "scene_visibility": "contextual",
            },
        },
        "phases": [
            {
                "phase_id": "daily",
                "title": "Daily Check-in",
                "objective": "Regelmaessige Statusmeldungen und Aufgabenerfuellung sicherstellen.",
                "guidance": "Fordere taegliche Check-ins ein und reagiere auf Compliance mit Lob, auf Nichteinhaltung mit klaren Konsequenzen.",
            }
        ],
        "lorebook": [],
    },
    {
        "key": "cold_structure",
        "title": "Cold Structure",
        "summary": "Nuechterne, klare Anleitung mit Fokus auf Regeltreue und Reporting.",
        "tags": ["discipline", "reporting", "tasks"],
        "behavior_profile": {
            "roleplay_defaults": {
                "relationship": {"strictness": 74, "control_level": "strict"},
                "protocol": {
                    "active_rules": ["Kurz und wahrheitsgemaess reporten", "Keine eigenmaechtigen Abweichungen"],
                },
            },
            "director": {
                "task_eagerness": "high",
                "state_update_aggressiveness": "high",
                "consequence_style": "strict",
                "scene_visibility": "minimal",
            },
            "reminder": {
                "max_sentences": 2,
            },
        },
        "phases": [
            {
                "phase_id": "active",
                "title": "Strukturphase",
                "objective": "Strikte Regeleinhaltung und lueckenloses Reporting.",
                "guidance": "Kurze, praezise Anweisungen. Abweichungen werden dokumentiert und konsequent bewertet.",
            }
        ],
        "lorebook": [],
    },
    {
        "key": "careful_progression",
        "title": "Careful Progression",
        "summary": "Sanfte, schrittweise Intensitaetssteuerung mit Safety-Prioritaet.",
        "tags": ["safety", "progression", "feedback"],
        "behavior_profile": {
            "roleplay_defaults": {
                "relationship": {"trust": 58, "strictness": 58},
                "protocol": {
                    "reward_focus": "Sicherheit, Feedback und stabile Gewoehnung",
                    "consequence_focus": "Anpassen, verlangsamen und klar rueckkoppeln",
                },
            },
            "director": {
                "task_eagerness": "balanced",
                "state_update_aggressiveness": "low",
                "consequence_style": "soft",
                "scene_visibility": "contextual",
            },
            "reminder": {
                "opening_soft": "Ruhig bleiben.",
                "max_sentences": 3,
            },
        },
        "phases": [
            {
                "phase_id": "intro",
                "title": "Eingewoehnungsphase",
                "objective": "Sanfte Intensitaetssteigerung mit regelmaessigem Feedback.",
                "guidance": "Schrittweise erhoehte Anforderungen, immer mit Rueckkanal fuer Wohlbefinden und Grenzen.",
            }
        ],
        "lorebook": [],
    },
]


# ── Pydantic models ──────────────────────────────────────────────────────────

class ScenarioCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=4000)
    lorebook: list = Field(default_factory=list)
    phases: list = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    behavior_profile: dict = Field(default_factory=dict)


class ScenarioUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    key: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=4000)
    lorebook: list | None = Field(default=None)
    phases: list | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    behavior_profile: dict | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _scenario_to_dict(s: Scenario) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "key": s.key,
        "summary": s.summary,
        "lorebook": json.loads(s.lorebook_json or "[]"),
        "phases": json.loads(s.phases_json or "[]"),
        "tags": json.loads(s.tags_json or "[]"),
        "behavior_profile": parse_behavior_profile(s.behavior_profile_json),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _auto_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "scenario"


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/presets")
def list_scenario_presets() -> dict:
    return {"items": SCENARIO_PRESETS}


@router.get("")
def list_scenarios(request: Request, db: Session = Depends(get_db)) -> dict:
    require_session_user(request, db)
    rows = db.query(Scenario).order_by(Scenario.id.asc()).all()
    return {"items": [_scenario_to_dict(s) for s in rows]}


@router.post("")
def create_scenario(payload: ScenarioCreateRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_session_user(request, db)
    key = payload.key.strip()
    if db.query(Scenario).filter(Scenario.key == key).first():
        raise HTTPException(status_code=409, detail=f"Scenario key '{key}' already exists")
    scenario = Scenario(
        title=payload.title.strip(),
        key=key,
        summary=payload.summary.strip() if payload.summary else None,
        lorebook_json=json.dumps(payload.lorebook, ensure_ascii=False),
        phases_json=json.dumps(payload.phases, ensure_ascii=False),
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
        behavior_profile_json=dumps_behavior_profile(payload.behavior_profile),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    audit_log("admin_scenario_created", actor_user_id=user.id, scenario_id=scenario.id, scenario_key=scenario.key)
    return _scenario_to_dict(scenario)


@router.get("/{scenario_id}")
def get_scenario(scenario_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    require_session_user(request, db)
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _scenario_to_dict(s)


@router.put("/{scenario_id}")
def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_session_user(request, db)
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if payload.title is not None:
        s.title = payload.title.strip()
    if payload.key is not None:
        new_key = payload.key.strip()
        conflict = db.query(Scenario).filter(Scenario.key == new_key, Scenario.id != scenario_id).first()
        if conflict:
            raise HTTPException(status_code=409, detail=f"Scenario key '{new_key}' already in use")
        s.key = new_key
    if payload.summary is not None:
        s.summary = payload.summary.strip() or None
    if payload.lorebook is not None:
        s.lorebook_json = json.dumps(payload.lorebook, ensure_ascii=False)
    if payload.phases is not None:
        s.phases_json = json.dumps(payload.phases, ensure_ascii=False)
    if payload.tags is not None:
        s.tags_json = json.dumps(payload.tags, ensure_ascii=False)
    if payload.behavior_profile is not None:
        s.behavior_profile_json = dumps_behavior_profile(payload.behavior_profile)
    db.add(s)
    db.commit()
    db.refresh(s)
    audit_log("admin_scenario_updated", actor_user_id=user.id, scenario_id=s.id, scenario_key=s.key)
    return _scenario_to_dict(s)


@router.delete("/{scenario_id}")
def delete_scenario(scenario_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_session_user(request, db)
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    deleted_key = s.key
    db.delete(s)
    db.commit()
    audit_log("admin_scenario_deleted", actor_user_id=user.id, scenario_id=scenario_id, scenario_key=deleted_key)
    return {"deleted": scenario_id}


@router.get("/{scenario_id}/export")
def export_scenario(scenario_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    require_admin_session_user(request, db)
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    card = {
        "schema_version": "0.1.2",
        "kind": "scenario_card",
        "title": s.title,
        "key": s.key,
        "summary": s.summary,
        "lorebook": json.loads(s.lorebook_json or "[]"),
        "phases": json.loads(s.phases_json or "[]"),
        "tags": json.loads(s.tags_json or "[]"),
        "behavior_profile": parse_behavior_profile(s.behavior_profile_json),
    }
    slug = re.sub(r"[^a-z0-9]+", "-", s.title.lower()).strip("-") or f"scenario-{s.id}"
    return JSONResponse(
        content=card,
        headers={"Content-Disposition": f'attachment; filename="scenario-{slug}.json"'},
    )


@router.post("/import")
async def import_scenario(request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_admin_session_user(request, db)
    body = await request.json()
    title = str(body.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=422, detail="'title' is required")
    key = str(body.get("key", "")).strip() or _auto_key(title)
    # Deduplicate key if needed
    base_key = key
    suffix = 2
    while db.query(Scenario).filter(Scenario.key == key).first():
        key = f"{base_key}_{suffix}"
        suffix += 1
    tags = body.get("tags") or body.get("focus") or []
    s = Scenario(
        title=title,
        key=key,
        summary=str(body.get("summary", "")).strip() or None,
        lorebook_json=json.dumps(body.get("lorebook") or [], ensure_ascii=False),
        phases_json=json.dumps(body.get("phases") or [], ensure_ascii=False),
        tags_json=json.dumps(list(tags), ensure_ascii=False),
        behavior_profile_json=dumps_behavior_profile(body.get("behavior_profile") if isinstance(body.get("behavior_profile"), dict) else {}),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    audit_log("admin_scenario_imported", actor_user_id=user.id, scenario_id=s.id, scenario_key=s.key)
    return _scenario_to_dict(s)
