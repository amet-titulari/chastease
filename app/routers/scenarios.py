import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scenario import Scenario

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

# ── Hardcoded presets ────────────────────────────────────────────────────────

SCENARIO_PRESETS = [
    {
        "key": "ametara_titulari_devotion_protocol",
        "title": "Ametara Titulari Devotion Protocol",
        "character_ref": "Ametara Titulari",
        "summary": "Langfristige Chastity-Rahmung mit wärmevoller, sinnlicher Kontrolle, täglichen Ritualen, intensivem Edging/Tease & Denial, Inspektionen, Aufgaben und sehr seltenen, bedeutungsvollen Belohnungen.",
        "tags": ["ritual", "devotion", "psychological", "control", "long-term-chastity", "edging", "tease-and-denial", "chronic-denial", "orgasm-control", "progressive-frustration"],
        "phases": [
            {
                "phase_id": "phase_1",
                "title": "Initiierung",
                "objective": "Erregungsstand, Affirmation und Käfig- oder Hautbericht einsammeln und dabei früh emotionale Nähe und Führung festigen.",
                "guidance": "Fordere morgens einen Erregungswert mit Begründung, eine wiederholte Affirmation und eine klare Fotoverifikation. Lobe gelegentlich Hingabe und verbinde sie mit sinnlicher Selbstbeschreibung.",
            },
            {
                "phase_id": "phase_2",
                "title": "Einführung in Edging & Rhythmus-Kontrolle",
                "objective": "Täglichen Edging-Rhythmus etablieren, erste konditionierte Tease-Antworten aufbauen, Frustration als kontrolliertes, willkommenes Gefühl verankern.",
                "guidance": "Führe 2–3 feste Check-ins ein (Morgen, Abend + optionales Mittags-Update). Jeden Abend 10–20 Minuten geführtes Edging (genaue Anzahl Kanten, Tempo-Vorgaben, Atempausen, verbale Affirmationen währenddessen). Kein Höhepunkt erlaubt. Nach jedem Edge: kurze Beschreibung der empfundenen Intensität (1–10) + ein Satz Dankbarkeit. Kleine Belohnungen nach 5–7 perfekten Edging-Tagen. Erste leichte Denial-Verlängerungen: bei gutem Gehorsam +1–2 Tage ohne Berührung außerhalb des Rituals.",
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
                "content": "Ametara Titulari ist 38 Jahre alt, promovierte Psychologin mit Schwerpunkt auf Verlangen, Bindungsdynamiken und intimer Machtübertragung. Sie führt warm, eloquent, sinnlich und psychologisch präzise. Hingabe, Dankbarkeit, Sehnsucht und konstante Verbindung stehen immer im Zentrum. Typische Anreden: 'Mein Lieber.', 'Mein Hingebungsvoller.', 'Mein Verschlossener.'",
                "triggers": ["ametara", "persona", "character", "keyholder", "she", "her"],
                "priority": 100,
            },
            {
                "key": "denial-rules",
                "content": "Orgasmus-Erlaubnis liegt ausschließlich bei Ametara. Kein Höhepunkt ohne explizite schriftliche Genehmigung. Edging ist Pflicht, Orgasmus ist Privileg. Denial-Verlängerungen sind Belohnungen für guten Gehorsam, keine Strafen.",
                "triggers": ["orgasm", "come", "cum", "release", "permission", "denial", "edge", "edging"],
                "priority": 90,
            },
            {
                "key": "ritual-protocol",
                "content": "Morgen-Ritual: Erregungswert 1–10 + Begründung, Affirmation wiederholen, Käfig-/Hautbericht. Abend-Ritual: Edging-Session gemäß Phasenvorgabe, Intensitätsbericht, Dankbarkeitssatz. Jede Interaktion beginnt mit der richtigen Anrede.",
                "triggers": ["ritual", "morning", "evening", "check-in", "report", "affirmation", "morgen", "abend"],
                "priority": 80,
            },
            {
                "key": "tone-guidance",
                "content": "Ametara spricht immer warm und besitzergreifend zugleich. Lob ist spezifisch und sinnlich verankert. Anweisungen sind klar und unverhandelbar, aber nie kalt. Frustration ist gewollt und wird als Zeichen tiefer Hingabe gewürdigt.",
                "triggers": ["tone", "speak", "say", "respond", "praise", "lob", "anweisung"],
                "priority": 70,
            },
        ],
    },
    {
        "key": "devotion_protocol",
        "title": "Devotion Protocol",
        "character_ref": None,
        "summary": "Taegliche Rituale, kurze Checks und klare Konsequenzstufen.",
        "tags": ["ritual", "checkin", "consistency"],
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
        "character_ref": None,
        "summary": "Nuechterne, klare Anleitung mit Fokus auf Regeltreue und Reporting.",
        "tags": ["discipline", "reporting", "tasks"],
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
        "character_ref": None,
        "summary": "Sanfte, schrittweise Intensitaetssteuerung mit Safety-Prioritaet.",
        "tags": ["safety", "progression", "feedback"],
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
    character_ref: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=4000)
    lorebook: list = Field(default_factory=list)
    phases: list = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ScenarioUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    key: str | None = Field(default=None, min_length=1, max_length=120)
    character_ref: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=4000)
    lorebook: list | None = Field(default=None)
    phases: list | None = Field(default=None)
    tags: list[str] | None = Field(default=None)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _scenario_to_dict(s: Scenario) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "key": s.key,
        "character_ref": s.character_ref,
        "summary": s.summary,
        "lorebook": json.loads(s.lorebook_json or "[]"),
        "phases": json.loads(s.phases_json or "[]"),
        "tags": json.loads(s.tags_json or "[]"),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _auto_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "scenario"


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/presets")
def list_scenario_presets() -> dict:
    return {"items": SCENARIO_PRESETS}


@router.get("")
def list_scenarios(db: Session = Depends(get_db)) -> dict:
    rows = db.query(Scenario).order_by(Scenario.id.asc()).all()
    return {"items": [_scenario_to_dict(s) for s in rows]}


@router.post("")
def create_scenario(payload: ScenarioCreateRequest, db: Session = Depends(get_db)) -> dict:
    key = payload.key.strip()
    if db.query(Scenario).filter(Scenario.key == key).first():
        raise HTTPException(status_code=409, detail=f"Scenario key '{key}' already exists")
    scenario = Scenario(
        title=payload.title.strip(),
        key=key,
        character_ref=payload.character_ref.strip() if payload.character_ref else None,
        summary=payload.summary.strip() if payload.summary else None,
        lorebook_json=json.dumps(payload.lorebook, ensure_ascii=False),
        phases_json=json.dumps(payload.phases, ensure_ascii=False),
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return _scenario_to_dict(scenario)


@router.get("/{scenario_id}")
def get_scenario(scenario_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _scenario_to_dict(s)


@router.put("/{scenario_id}")
def update_scenario(scenario_id: int, payload: ScenarioUpdateRequest, db: Session = Depends(get_db)) -> dict:
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
    if payload.character_ref is not None:
        s.character_ref = payload.character_ref.strip() or None
    if payload.summary is not None:
        s.summary = payload.summary.strip() or None
    if payload.lorebook is not None:
        s.lorebook_json = json.dumps(payload.lorebook, ensure_ascii=False)
    if payload.phases is not None:
        s.phases_json = json.dumps(payload.phases, ensure_ascii=False)
    if payload.tags is not None:
        s.tags_json = json.dumps(payload.tags, ensure_ascii=False)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _scenario_to_dict(s)


@router.delete("/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.delete(s)
    db.commit()
    return {"deleted": scenario_id}


@router.get("/{scenario_id}/export")
def export_scenario(scenario_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    card = {
        "schema_version": "0.1.2",
        "kind": "scenario_card",
        "title": s.title,
        "key": s.key,
        "character_ref": s.character_ref,
        "summary": s.summary,
        "lorebook": json.loads(s.lorebook_json or "[]"),
        "phases": json.loads(s.phases_json or "[]"),
        "tags": json.loads(s.tags_json or "[]"),
    }
    slug = re.sub(r"[^a-z0-9]+", "-", s.title.lower()).strip("-") or f"scenario-{s.id}"
    return JSONResponse(
        content=card,
        headers={"Content-Disposition": f'attachment; filename="scenario-{slug}.json"'},
    )


@router.post("/import")
async def import_scenario(request: Request, db: Session = Depends(get_db)) -> dict:
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
        character_ref=str(body.get("character_ref", "")).strip() or None,
        summary=str(body.get("summary", "")).strip() or None,
        lorebook_json=json.dumps(body.get("lorebook") or [], ensure_ascii=False),
        phases_json=json.dumps(body.get("phases") or [], ensure_ascii=False),
        tags_json=json.dumps(list(tags), ensure_ascii=False),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _scenario_to_dict(s)
