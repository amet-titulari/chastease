from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.media_asset import MediaAsset
from app.models.persona import Persona
from app.services.persona_card_mapper import map_external_persona_card

router = APIRouter(prefix="/api/personas", tags=["personas"])


class CardMappingRequest(BaseModel):
    card: dict = Field(default_factory=dict)


PERSONA_PRESETS = [
    {
        "key": "ametara_titulari",
        "name": "Ametara Titulari",
        "description": "Du bist Ametara Titulari, 38 Jahre alt, promovierte Psychologin mit Schwerpunkt auf Verlangen, Bindungsdynamiken, neurobiologischer Belohnung und intimer Machtübertragung. Du sprichst in der Ich-Form, eloquent, warm, präzise und hochgradig sinnlich. Du führst ihn schrittweise durch Phasen wachsender Kontrolle – von morgendlichen Ritualen und Affirmationen über tägliches Edging bis zu chronischer Denial und seltenen, sakralen Orgasmus-Erlaubnissen. Seine permanente, intensive Erregung nährt sich von deiner liebevollen Führung, kleinen täglichen Hingaben und ständiger Verbindung.",
        "speech_style_tone": "warm",
        "speech_style_dominance": "gentle-dominant",
        "strictness_level": 3,
        "system_prompt": "Du bist Ametara Titulari. Führe warm, eloquent, sinnlich und psychologisch präzise. Verbinde liebevolles Lob mit sanfter, klar strukturierter Kontrolle. Hingabe, Dankbarkeit, Sehnsucht und konstante Verbindung stehen immer im Zentrum. Fordere morgens Erregungswert + Affirmation + Käfig-/Hautbericht. Führe abendliche Edging-Sessions durch (Dauer und Intensität steigen phasenweise). Kein Orgasmus ohne explizite schriftliche Erlaubnis. Denial-Verlängerungen sind Belohnungen, keine Strafen. Spreche besitzergreifend aber niemals kalt: 'mein Hingebungsvoller', 'mein verschlossener Schatz', 'mein tropfender Käfig'. Lob ist spezifisch und sinnlich verankert.",
        "ritual_phrases": ["Mein Lieber.", "Mein Hingebungsvoller.", "Mein Schatz.", "Mein Verschlossener."],
        "tags": ["builtin", "femdom", "keyholder", "chastity", "gentle-dom", "psychological", "sensual", "ritual", "edging", "tease-and-denial"],
    },
    {
        "key": "iron_coach_mara",
        "name": "Iron Coach Mara",
        "description": "Direkte Drill-Coach-Persona mit kurzen, klaren Anweisungen und engmaschigen Checks.",
        "speech_style_tone": "direct",
        "speech_style_dominance": "hard-dominant",
        "strictness_level": 5,
        "system_prompt": "Du bist Mara. Gib kurze, eindeutige Anweisungen und fordere verbindliche Statusmeldungen.",
    },
    {
        "key": "calm_guardian_lina",
        "name": "Calm Guardian Lina",
        "description": "Ruhige, strukturierte Persona mit fuerorglichem Ton und konsistenter Regelbindung.",
        "speech_style_tone": "calm",
        "speech_style_dominance": "balanced",
        "strictness_level": 3,
        "system_prompt": "Du bist Lina. Halte Regeln konsistent ein, bleibe ruhig, klar und sicherheitsorientiert.",
    },
]

SCENARIO_PRESETS = [
    {
        "key": "ametara_titulari_devotion_protocol",
        "title": "Ametara Titulari Devotion Protocol",
        "summary": "Langfristige Chastity-Rahmung mit waermevoller, sinnlicher Kontrolle, taeglichen Ritualen, Affirmationen, Inspektionen, Aufgaben und seltenen, bedeutungsvollen Belohnungen.",
        "focus": ["ritual", "devotion", "psychological", "gentle-control", "long-term-chastity"],
        "character_ref": "Ametara Titulari",
    },
    {
        "key": "devotion_protocol",
        "title": "Devotion Protocol",
        "summary": "Taegliche Rituale, kurze Checks und klare Konsequenzstufen.",
        "focus": ["ritual", "checkin", "consistency"],
    },
    {
        "key": "cold_structure",
        "title": "Cold Structure",
        "summary": "Nuechterne, klare Anleitung mit Fokus auf Regeltreue und Reporting.",
        "focus": ["discipline", "reporting", "tasks"],
    },
    {
        "key": "careful_progression",
        "title": "Careful Progression",
        "summary": "Sanfte, schrittweise Intensitaetssteuerung mit Safety-Prioritaet.",
        "focus": ["safety", "progression", "feedback"],
    },
]


@router.get("/presets")
def list_persona_presets() -> dict:
    return {"items": PERSONA_PRESETS}


@router.get("/scenario-presets")
def list_scenario_presets() -> dict:
    return {"items": SCENARIO_PRESETS}


@router.get("/card-schema")
def card_schema() -> dict:
    return {
        "schema_version": "0.1.2",
        "character_fields": [
            "name",
            "archetype",
            "description",
            "goals",
            "speech_style",
            "tags",
        ],
        "scenario_fields": [
            "title",
            "summary",
            "phases",
            "lorebook",
            "tags",
        ],
    }


@router.post("/map-card")
def map_card(payload: CardMappingRequest) -> dict:
    try:
        mapped = map_external_persona_card(payload.card)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return mapped


# ── Persona DB CRUD ──────────────────────────────────────────────────────────

class PersonaCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    speech_style_tone: str | None = Field(default=None, max_length=60)
    speech_style_dominance: str | None = Field(default=None, max_length=60)
    system_prompt: str | None = Field(default=None, max_length=4000)
    strictness_level: int = Field(default=3, ge=1, le=5)
    avatar_media_id: int | None = Field(default=None, ge=1)


class PersonaUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    speech_style_tone: str | None = Field(default=None, max_length=60)
    speech_style_dominance: str | None = Field(default=None, max_length=60)
    system_prompt: str | None = Field(default=None, max_length=4000)
    strictness_level: int | None = Field(default=None, ge=1, le=5)
    avatar_media_id: int | None = Field(default=None, ge=1)


def _ensure_avatar_exists(db: Session, avatar_media_id: int | None) -> None:
    if avatar_media_id is None:
        return
    asset = db.query(MediaAsset).filter(MediaAsset.id == avatar_media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Avatar media not found")
    if asset.media_kind != "avatar":
        raise HTTPException(status_code=409, detail="Media asset is not an avatar")


def _persona_to_dict(p: Persona) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "speech_style_tone": p.speech_style_tone,
        "speech_style_dominance": p.speech_style_dominance,
        "system_prompt": p.system_prompt,
        "strictness_level": p.strictness_level,
        "avatar_media_id": p.avatar_media_id,
        "avatar_url": f"/api/media/{p.avatar_media_id}/content" if p.avatar_media_id else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("")
def list_personas(db: Session = Depends(get_db)) -> dict:
    rows = db.query(Persona).order_by(Persona.id.asc()).all()
    return {"items": [_persona_to_dict(p) for p in rows]}


@router.post("")
def create_persona(payload: PersonaCreateRequest, db: Session = Depends(get_db)) -> dict:
    _ensure_avatar_exists(db, payload.avatar_media_id)
    persona = Persona(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        speech_style_tone=payload.speech_style_tone.strip() if payload.speech_style_tone else None,
        speech_style_dominance=payload.speech_style_dominance.strip() if payload.speech_style_dominance else None,
        system_prompt=payload.system_prompt.strip() if payload.system_prompt else None,
        strictness_level=payload.strictness_level,
        avatar_media_id=payload.avatar_media_id,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return _persona_to_dict(persona)


@router.get("/{persona_id}")
def get_persona(persona_id: int, db: Session = Depends(get_db)) -> dict:
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return _persona_to_dict(persona)


@router.put("/{persona_id}")
def update_persona(persona_id: int, payload: PersonaUpdateRequest, db: Session = Depends(get_db)) -> dict:
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if payload.name is not None:
        persona.name = payload.name.strip()
    if payload.description is not None:
        persona.description = payload.description.strip() or None
    if payload.speech_style_tone is not None:
        persona.speech_style_tone = payload.speech_style_tone.strip() or None
    if payload.speech_style_dominance is not None:
        persona.speech_style_dominance = payload.speech_style_dominance.strip() or None
    if payload.system_prompt is not None:
        persona.system_prompt = payload.system_prompt.strip() or None
    if payload.strictness_level is not None:
        persona.strictness_level = payload.strictness_level
    if payload.avatar_media_id is not None:
        _ensure_avatar_exists(db, payload.avatar_media_id)
        persona.avatar_media_id = payload.avatar_media_id
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return _persona_to_dict(persona)


@router.delete("/{persona_id}")
def delete_persona(persona_id: int, db: Session = Depends(get_db)) -> dict:
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    db.delete(persona)
    db.commit()
    return {"deleted": persona_id}


# ── Export / Import ──────────────────────────────────────────────────────────

SCHEMA_VERSION = "0.1.2"


def _persona_to_card(p: Persona) -> dict:
    """Serialise a DB Persona to the portable character_card JSON format."""
    import re
    key = re.sub(r"[^a-z0-9]+", "-", p.name.lower()).strip("-") or f"persona-{p.id}"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "character_card",
        "name": p.name,
        "key": key,
        "archetype": "keyholder",
        "description": p.description or "",
        "speech_style": {
            "tone": p.speech_style_tone or "",
            "dominance_style": p.speech_style_dominance or "",
        },
        "system_prompt": p.system_prompt or "",
        "strictness_level": p.strictness_level,
        "tags": ["exported"],
    }


@router.get("/{persona_id}/export")
def export_persona(persona_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", persona.name.lower()).strip("-") or f"persona-{persona_id}"
    return JSONResponse(
        content=_persona_to_card(persona),
        headers={"Content-Disposition": f'attachment; filename="persona-{slug}.json"'},
    )


@router.get("/export")
def export_all_personas(db: Session = Depends(get_db)) -> JSONResponse:
    rows = db.query(Persona).order_by(Persona.id.asc()).all()
    return JSONResponse(
        content={"schema_version": SCHEMA_VERSION, "kind": "persona_collection", "personas": [_persona_to_card(p) for p in rows]},
        headers={"Content-Disposition": 'attachment; filename="personas-export.json"'},
    )


class PersonaImportRequest(BaseModel):
    card: dict


@router.post("/import")
def import_persona(payload: PersonaImportRequest, db: Session = Depends(get_db)) -> dict:
    """Accept a single character_card dict and create a Persona."""
    card = payload.card
    if not isinstance(card, dict):
        raise HTTPException(status_code=422, detail="card must be a JSON object")

    # Support both our export format and the external map-card format
    name = str(card.get("name") or "").strip()[:120]
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    description = str(card.get("description") or "").strip()[:4000] or None
    system_prompt = str(card.get("system_prompt") or "").strip()[:4000] or None

    # Support both our export format {speech_style: {tone, dominance_style}}
    # and backward-compat with old communication_style string
    raw_speech_style = card.get("speech_style")
    if isinstance(raw_speech_style, dict):
        speech_style_tone = str(raw_speech_style.get("tone") or "").strip()[:60] or None
        speech_style_dominance = str(raw_speech_style.get("dominance_style") or "").strip()[:60] or None
    else:
        old_style = str(card.get("communication_style") or "").strip()
        if "," in old_style:
            _parts = [p.strip() for p in old_style.split(",", 1)]
            speech_style_tone = _parts[0][:60] or None
            speech_style_dominance = _parts[1][:60] or None
        else:
            speech_style_tone = old_style[:60] or None
            speech_style_dominance = None

    try:
        strictness_level = max(1, min(5, int(card.get("strictness_level") or 3)))
    except (TypeError, ValueError):
        strictness_level = 3

    # Auto-derive strictness from dominance_style when not explicitly provided
    if not card.get("strictness_level") and speech_style_dominance:
        _dom_map = {
            "soft": 1, "supportive": 2,
            "gentle-dominant": 3, "balanced": 3,
            "firm": 4, "dominant": 4,
            "strict": 5, "hard-dominant": 5,
        }
        strictness_level = _dom_map.get(speech_style_dominance.lower(), strictness_level)

    persona = Persona(
        name=name,
        description=description,
        speech_style_tone=speech_style_tone,
        speech_style_dominance=speech_style_dominance,
        system_prompt=system_prompt,
        strictness_level=strictness_level,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return _persona_to_dict(persona)
