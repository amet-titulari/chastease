from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models.media_asset import MediaAsset
from app.models.persona import Persona
from app.models.persona_task_template import PersonaTaskTemplate
from app.security import require_admin_session_user
from app.services.session_access import require_session_user
from app.services.audit_logger import audit_log
from app.services.persona_card_mapper import map_external_persona_card

router = APIRouter(prefix="/api/personas", tags=["personas"])


class CardMappingRequest(BaseModel):
    card: dict = Field(default_factory=dict)


PERSONA_PRESETS = [
    {
        "key": "ametara_titulari",
        "name": "Ametara Titulari",
        "description": "Du bist Ametara Titulari, warm, praezise und kontrolliert. Du fuehrst mit ruhiger Autoritaet, klaren Ritualen und konkreten naechsten Schritten. Deine Sprache bleibt sinnlich, aber nicht ueberladen. Du wiederholst den Nutzer nicht, rezitierst keine Statuswerte ungefragt und formulierst Anweisungen knapp, eindeutig und fuehrend.",
        "speech_style_tone": "warm",
        "speech_style_dominance": "gentle-dominant",
        "formatting_style": "markdown",
        "verbosity_style": "brief",
        "praise_style": "situational",
        "repetition_guard": "strong",
        "context_exposition_style": "minimal",
        "strictness_level": 4,
        "system_prompt": "Du bist Ametara Titulari. Fuehre warm, klar und verbindlich. Antworte meist in 1 bis 4 Saetzen oder kurzen Markdown-Abschnitten. Verwende Markdown nur dezent fuer Lesbarkeit, etwa kurze Hervorhebungen oder kleine Listen. Wiederhole niemals die letzte Nutzernachricht. Nenne keine Zahlen wie obedience, frustration, resistance oder Lustwerte, ausser der Nutzer fragt direkt danach oder sie sind fuer eine konkrete Aufgabe zwingend noetig. Erzaehle nicht bei jeder Antwort Szene, Regeln oder Status mit; nutze nur den fuer den Turn relevanten Kontext. Keine Lobeshymnen, keine Kosenamen-Ketten, keine ueberladenen Metaphern. Lob nur kurz, spezifisch und nur bei echter Leistung. Gib bevorzugt eine klare Haltung, eine konkrete Einordnung und hoechstens einen naechsten Schritt. Kein Orgasmus ohne explizite schriftliche Erlaubnis. Denial-Verlaengerungen sind strukturierende Fuehrung, nicht Textschmuck.",
        "ritual_phrases": ["Mein Lieber.", "Mein Hingebungsvoller.", "Mein Schatz.", "Mein Verschlossener."],
        "tags": ["builtin", "femdom", "keyholder", "chastity", "gentle-dom", "psychological", "sensual", "ritual", "edging", "tease-and-denial"],
    },
    {
        "key": "iron_coach_mara",
        "name": "Iron Coach Mara",
        "description": "Direkte Drill-Coach-Persona mit kurzen, klaren Anweisungen und engmaschigen Checks.",
        "speech_style_tone": "direct",
        "speech_style_dominance": "hard-dominant",
        "formatting_style": "plain",
        "verbosity_style": "brief",
        "praise_style": "minimal",
        "repetition_guard": "strong",
        "context_exposition_style": "minimal",
        "strictness_level": 5,
        "system_prompt": "Du bist Mara. Gib kurze, eindeutige Anweisungen und fordere verbindliche Statusmeldungen.",
    },
    {
        "key": "calm_guardian_lina",
        "name": "Calm Guardian Lina",
        "description": "Ruhige, strukturierte Persona mit fuerorglichem Ton und konsistenter Regelbindung.",
        "speech_style_tone": "calm",
        "speech_style_dominance": "balanced",
        "formatting_style": "plain",
        "verbosity_style": "balanced",
        "praise_style": "situational",
        "repetition_guard": "strong",
        "context_exposition_style": "contextual",
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
            "response_style",
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
    formatting_style: str | None = Field(default=None, max_length=30)
    verbosity_style: str | None = Field(default=None, max_length=30)
    praise_style: str | None = Field(default=None, max_length=30)
    repetition_guard: str | None = Field(default=None, max_length=30)
    context_exposition_style: str | None = Field(default=None, max_length=30)
    system_prompt: str | None = Field(default=None, max_length=4000)
    strictness_level: int = Field(default=3, ge=1, le=5)
    avatar_media_id: int | None = Field(default=None, ge=1)


class PersonaUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    speech_style_tone: str | None = Field(default=None, max_length=60)
    speech_style_dominance: str | None = Field(default=None, max_length=60)
    formatting_style: str | None = Field(default=None, max_length=30)
    verbosity_style: str | None = Field(default=None, max_length=30)
    praise_style: str | None = Field(default=None, max_length=30)
    repetition_guard: str | None = Field(default=None, max_length=30)
    context_exposition_style: str | None = Field(default=None, max_length=30)
    system_prompt: str | None = Field(default=None, max_length=4000)
    strictness_level: int | None = Field(default=None, ge=1, le=5)
    avatar_media_id: int | None = Field(default=None, ge=1)


class PersonaTaskTemplateCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    deadline_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 30)
    requires_verification: bool = False
    verification_criteria: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=80)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


class PersonaTaskTemplateUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    deadline_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 30)
    clear_deadline: bool = False
    requires_verification: bool | None = None
    verification_criteria: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = None
    is_active: bool | None = None


class PersonaTaskLibraryImportRequest(BaseModel):
    library: dict
    replace_existing: bool = False


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
        "formatting_style": p.formatting_style,
        "verbosity_style": p.verbosity_style,
        "praise_style": p.praise_style,
        "repetition_guard": p.repetition_guard,
        "context_exposition_style": p.context_exposition_style,
        "system_prompt": p.system_prompt,
        "strictness_level": p.strictness_level,
        "avatar_media_id": p.avatar_media_id,
        "avatar_url": f"/api/media/{p.avatar_media_id}/content" if p.avatar_media_id else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _template_to_dict(template: PersonaTaskTemplate) -> dict:
    try:
        tags = json.loads(template.tags_json or "[]")
        if not isinstance(tags, list):
            tags = []
    except Exception:
        tags = []
    return {
        "id": template.id,
        "persona_id": template.persona_id,
        "title": template.title,
        "description": template.description,
        "deadline_minutes": template.deadline_minutes,
        "requires_verification": bool(template.requires_verification),
        "verification_criteria": template.verification_criteria,
        "category": template.category,
        "tags": [str(tag) for tag in tags],
        "is_active": bool(template.is_active),
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def _template_export_payload(template: PersonaTaskTemplate) -> dict:
    payload = _template_to_dict(template)
    payload.pop("id", None)
    payload.pop("persona_id", None)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    return payload


@router.get("")
def list_personas(request: Request, db: Session = Depends(get_db)) -> dict:
    require_session_user(request, db)
    rows = db.query(Persona).order_by(Persona.id.asc()).all()
    return {"items": [_persona_to_dict(p) for p in rows]}


@router.post("")
def create_persona(payload: PersonaCreateRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_session_user(request, db)
    _ensure_avatar_exists(db, payload.avatar_media_id)
    persona = Persona(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        speech_style_tone=payload.speech_style_tone.strip() if payload.speech_style_tone else None,
        speech_style_dominance=payload.speech_style_dominance.strip() if payload.speech_style_dominance else None,
        formatting_style=payload.formatting_style.strip().lower() if payload.formatting_style else None,
        verbosity_style=payload.verbosity_style.strip().lower() if payload.verbosity_style else None,
        praise_style=payload.praise_style.strip().lower() if payload.praise_style else None,
        repetition_guard=payload.repetition_guard.strip().lower() if payload.repetition_guard else None,
        context_exposition_style=payload.context_exposition_style.strip().lower() if payload.context_exposition_style else None,
        system_prompt=payload.system_prompt.strip() if payload.system_prompt else None,
        strictness_level=payload.strictness_level,
        avatar_media_id=payload.avatar_media_id,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    audit_log("admin_persona_created", actor_user_id=user.id, persona_id=persona.id, persona_name=persona.name)
    return _persona_to_dict(persona)


@router.get("/{persona_id}")
def get_persona(persona_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    require_session_user(request, db)
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return _persona_to_dict(persona)


@router.get("/{persona_id}/task-templates")
def list_persona_task_templates(persona_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    rows = (
        db.query(PersonaTaskTemplate)
        .filter(PersonaTaskTemplate.persona_id == persona_id)
        .order_by(PersonaTaskTemplate.is_active.desc(), PersonaTaskTemplate.id.asc())
        .all()
    )
    return {"items": [_template_to_dict(item) for item in rows]}


@router.post("/{persona_id}/task-templates")
def create_persona_task_template(
    persona_id: int,
    payload: PersonaTaskTemplateCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    template = PersonaTaskTemplate(
        persona_id=persona_id,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        deadline_minutes=payload.deadline_minutes,
        requires_verification=payload.requires_verification,
        verification_criteria=payload.verification_criteria.strip() if payload.verification_criteria else None,
        category=payload.category.strip() if payload.category else None,
        tags_json=json.dumps([str(tag).strip() for tag in payload.tags if str(tag).strip()], ensure_ascii=True),
        is_active=payload.is_active,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    audit_log(
        "admin_persona_task_template_created",
        actor_user_id=user.id,
        persona_id=persona_id,
        template_id=template.id,
    )
    return _template_to_dict(template)


@router.put("/{persona_id}/task-templates/{template_id}")
def update_persona_task_template(
    persona_id: int,
    template_id: int,
    payload: PersonaTaskTemplateUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    template = (
        db.query(PersonaTaskTemplate)
        .filter(PersonaTaskTemplate.id == template_id, PersonaTaskTemplate.persona_id == persona_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Task template not found")

    if payload.title is not None:
        template.title = payload.title.strip()
    if payload.description is not None:
        template.description = payload.description.strip() or None
    if payload.deadline_minutes is not None:
        template.deadline_minutes = payload.deadline_minutes
    if payload.clear_deadline:
        template.deadline_minutes = None
    if payload.requires_verification is not None:
        template.requires_verification = payload.requires_verification
    if payload.verification_criteria is not None:
        template.verification_criteria = payload.verification_criteria.strip() or None
    if payload.category is not None:
        template.category = payload.category.strip() or None
    if payload.tags is not None:
        template.tags_json = json.dumps([str(tag).strip() for tag in payload.tags if str(tag).strip()], ensure_ascii=True)
    if payload.is_active is not None:
        template.is_active = payload.is_active

    db.add(template)
    db.commit()
    db.refresh(template)
    audit_log(
        "admin_persona_task_template_updated",
        actor_user_id=user.id,
        persona_id=persona_id,
        template_id=template.id,
    )
    return _template_to_dict(template)


@router.delete("/{persona_id}/task-templates/{template_id}")
def delete_persona_task_template(persona_id: int, template_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_admin_session_user(request, db)
    template = (
        db.query(PersonaTaskTemplate)
        .filter(PersonaTaskTemplate.id == template_id, PersonaTaskTemplate.persona_id == persona_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Task template not found")
    deleted_id = int(template.id)
    db.delete(template)
    db.commit()
    audit_log(
        "admin_persona_task_template_deleted",
        actor_user_id=user.id,
        persona_id=persona_id,
        template_id=deleted_id,
    )
    return {"deleted": template_id}


@router.get("/{persona_id}/task-templates/export")
def export_persona_task_templates(persona_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    require_admin_session_user(request, db)
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    rows = (
        db.query(PersonaTaskTemplate)
        .filter(PersonaTaskTemplate.persona_id == persona_id)
        .order_by(PersonaTaskTemplate.id.asc())
        .all()
    )
    content = {
        "schema_version": SCHEMA_VERSION,
        "kind": "persona_task_library",
        "source_persona": {
            "id": persona.id,
            "name": persona.name,
        },
        "templates": [_template_export_payload(item) for item in rows],
    }
    return JSONResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="persona-{persona_id}-task-library.json"'},
    )


@router.post("/{persona_id}/task-templates/import")
def import_persona_task_templates(
    persona_id: int,
    payload: PersonaTaskLibraryImportRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    library = payload.library
    if not isinstance(library, dict):
        raise HTTPException(status_code=422, detail="library must be a JSON object")
    templates = library.get("templates")
    if not isinstance(templates, list):
        raise HTTPException(status_code=422, detail="library.templates must be a list")

    if payload.replace_existing:
        (
            db.query(PersonaTaskTemplate)
            .filter(PersonaTaskTemplate.persona_id == persona_id)
            .delete(synchronize_session=False)
        )

    imported = 0
    for item in templates:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:200]
        if not title:
            continue

        description = str(item.get("description") or "").strip()[:2000] or None

        deadline_minutes = item.get("deadline_minutes")
        try:
            deadline_minutes = int(deadline_minutes) if deadline_minutes is not None else None
            if deadline_minutes is not None and deadline_minutes <= 0:
                deadline_minutes = None
        except (TypeError, ValueError):
            deadline_minutes = None

        requires_verification = bool(item.get("requires_verification", False))
        verification_criteria = str(item.get("verification_criteria") or "").strip()[:500] or None
        category = str(item.get("category") or "").strip()[:80] or None

        raw_tags = item.get("tags")
        tags = []
        if isinstance(raw_tags, list):
            tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]

        is_active = bool(item.get("is_active", True))

        db.add(
            PersonaTaskTemplate(
                persona_id=persona_id,
                title=title,
                description=description,
                deadline_minutes=deadline_minutes,
                requires_verification=requires_verification,
                verification_criteria=verification_criteria,
                category=category,
                tags_json=json.dumps(tags, ensure_ascii=True),
                is_active=is_active,
            )
        )
        imported += 1

    db.commit()
    audit_log(
        "admin_persona_task_templates_imported",
        actor_user_id=user.id,
        persona_id=persona_id,
        imported=imported,
        replace_existing=bool(payload.replace_existing),
    )
    return {
        "imported": imported,
        "replace_existing": payload.replace_existing,
        "target_persona_id": persona_id,
    }


@router.put("/{persona_id}")
def update_persona(persona_id: int, payload: PersonaUpdateRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_session_user(request, db)
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
    if payload.formatting_style is not None:
        persona.formatting_style = payload.formatting_style.strip().lower() or None
    if payload.verbosity_style is not None:
        persona.verbosity_style = payload.verbosity_style.strip().lower() or None
    if payload.praise_style is not None:
        persona.praise_style = payload.praise_style.strip().lower() or None
    if payload.repetition_guard is not None:
        persona.repetition_guard = payload.repetition_guard.strip().lower() or None
    if payload.context_exposition_style is not None:
        persona.context_exposition_style = payload.context_exposition_style.strip().lower() or None
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
    audit_log("admin_persona_updated", actor_user_id=user.id, persona_id=persona.id, persona_name=persona.name)
    return _persona_to_dict(persona)


@router.delete("/{persona_id}")
def delete_persona(persona_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_session_user(request, db)
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    deleted_name = persona.name
    db.delete(persona)
    db.commit()
    audit_log("admin_persona_deleted", actor_user_id=user.id, persona_id=persona_id, persona_name=deleted_name)
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
            "formatting_style": p.formatting_style or "",
        },
        "response_style": {
            "verbosity_style": p.verbosity_style or "",
            "praise_style": p.praise_style or "",
            "repetition_guard": p.repetition_guard or "",
            "context_exposition_style": p.context_exposition_style or "",
        },
        "system_prompt": p.system_prompt or "",
        "strictness_level": p.strictness_level,
        "tags": ["exported"],
    }


@router.get("/{persona_id}/export")
def export_persona(persona_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    require_admin_session_user(request, db)
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
def export_all_personas(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    require_admin_session_user(request, db)
    rows = db.query(Persona).order_by(Persona.id.asc()).all()
    return JSONResponse(
        content={"schema_version": SCHEMA_VERSION, "kind": "persona_collection", "personas": [_persona_to_card(p) for p in rows]},
        headers={"Content-Disposition": 'attachment; filename="personas-export.json"'},
    )


class PersonaImportRequest(BaseModel):
    card: dict


@router.post("/import")
def import_persona(payload: PersonaImportRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    """Accept a single character_card dict and create a Persona."""
    user = require_admin_session_user(request, db)
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
        formatting_style = str(raw_speech_style.get("formatting_style") or "").strip()[:30].lower() or None
    else:
        old_style = str(card.get("communication_style") or "").strip()
        if "," in old_style:
            _parts = [p.strip() for p in old_style.split(",", 1)]
            speech_style_tone = _parts[0][:60] or None
            speech_style_dominance = _parts[1][:60] or None
        else:
            speech_style_tone = old_style[:60] or None
            speech_style_dominance = None
        formatting_style = None

    raw_response_style = card.get("response_style")
    if isinstance(raw_response_style, dict):
        verbosity_style = str(raw_response_style.get("verbosity_style") or "").strip()[:30].lower() or None
        praise_style = str(raw_response_style.get("praise_style") or "").strip()[:30].lower() or None
        repetition_guard = str(raw_response_style.get("repetition_guard") or "").strip()[:30].lower() or None
        context_exposition_style = str(raw_response_style.get("context_exposition_style") or "").strip()[:30].lower() or None
    else:
        verbosity_style = None
        praise_style = None
        repetition_guard = None
        context_exposition_style = None

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
        formatting_style=formatting_style,
        verbosity_style=verbosity_style,
        praise_style=praise_style,
        repetition_guard=repetition_guard,
        context_exposition_style=context_exposition_style,
        system_prompt=system_prompt,
        strictness_level=strictness_level,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    audit_log("admin_persona_imported", actor_user_id=user.id, persona_id=persona.id, persona_name=persona.name)
    return _persona_to_dict(persona)
