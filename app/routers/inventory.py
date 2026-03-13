import json
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.item import Item
from app.models.scenario import Scenario
from app.models.scenario_item import ScenarioItem
from app.models.session import Session as SessionModel
from app.models.session_item import SessionItem

router = APIRouter(prefix="/api/inventory", tags=["inventory"])
SCHEMA_VERSION = "0.1.0"


class ItemCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


class ItemUpdateRequest(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = Field(default=None)
    is_active: bool | None = None


class ItemImportRequest(BaseModel):
    card: dict


class ScenarioInventoryEntry(BaseModel):
    item_id: int = Field(ge=1)
    is_required: bool = False
    default_quantity: int = Field(default=1, ge=1)
    notes: str | None = Field(default=None, max_length=2000)
    phase_id: str | None = Field(default=None, max_length=120)


class ScenarioInventoryReplaceRequest(BaseModel):
    entries: list[ScenarioInventoryEntry] = Field(default_factory=list)


class SessionInventoryCreateRequest(BaseModel):
    item_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1)
    status: str = Field(default="available", max_length=30)
    is_equipped: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    linked_scenario_item_id: int | None = Field(default=None, ge=1)


class SessionInventoryUpdateRequest(BaseModel):
    quantity: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, max_length=30)
    is_equipped: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


def _normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9_\-]+", "_", value.strip().lower()).strip("_")


def _item_to_card(item: Item) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "item_card",
        "key": item.key,
        "name": item.name,
        "category": item.category,
        "description": item.description,
        "tags": json.loads(item.tags_json or "[]"),
        "is_active": bool(item.is_active),
    }


def _unique_item_key(db: Session, key: str, ignore_item_id: int | None = None) -> str:
    candidate = _normalise_key(key)
    if not candidate:
        candidate = "item"
    if ignore_item_id is not None:
        exists = db.query(Item).filter(Item.key == candidate, Item.id != ignore_item_id).first()
    else:
        exists = db.query(Item).filter(Item.key == candidate).first()
    if not exists:
        return candidate

    for idx in range(2, 1000):
        alt = f"{candidate}_{idx}"
        if ignore_item_id is not None:
            exists = db.query(Item).filter(Item.key == alt, Item.id != ignore_item_id).first()
        else:
            exists = db.query(Item).filter(Item.key == alt).first()
        if not exists:
            return alt
    raise HTTPException(status_code=409, detail="Unable to allocate unique item key")


def _item_to_dict(item: Item) -> dict:
    return {
        "id": item.id,
        "key": item.key,
        "name": item.name,
        "category": item.category,
        "description": item.description,
        "tags": json.loads(item.tags_json or "[]"),
        "is_active": bool(item.is_active),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _scenario_item_to_dict(link: ScenarioItem, item: Item) -> dict:
    return {
        "scenario_item_id": link.id,
        "scenario_id": link.scenario_id,
        "item": _item_to_dict(item),
        "is_required": bool(link.is_required),
        "default_quantity": link.default_quantity,
        "notes": link.notes,
        "phase_id": link.phase_id,
    }


def _session_item_to_dict(link: SessionItem, item: Item) -> dict:
    return {
        "session_item_id": link.id,
        "session_id": link.session_id,
        "item": _item_to_dict(item),
        "quantity": link.quantity,
        "status": link.status,
        "is_equipped": bool(link.is_equipped),
        "notes": link.notes,
        "linked_scenario_item_id": link.linked_scenario_item_id,
        "created_at": link.created_at.isoformat() if link.created_at else None,
        "updated_at": link.updated_at.isoformat() if link.updated_at else None,
    }


@router.get("/items")
def list_items(include_inactive: bool = False, db: Session = Depends(get_db)) -> dict:
    query = db.query(Item)
    if not include_inactive:
        query = query.filter(Item.is_active == True)  # noqa: E712
    rows = query.order_by(Item.name.asc()).all()
    return {"items": [_item_to_dict(row) for row in rows]}


@router.post("/items")
def create_item(payload: ItemCreateRequest, db: Session = Depends(get_db)) -> dict:
    key = _normalise_key(payload.key)
    if not key:
        raise HTTPException(status_code=422, detail="Invalid item key")
    if db.query(Item).filter(Item.key == key).first():
        raise HTTPException(status_code=409, detail=f"Item key '{key}' already exists")

    row = Item(
        key=key,
        name=payload.name.strip(),
        category=payload.category.strip() if payload.category else None,
        description=payload.description.strip() if payload.description else None,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
        is_active=bool(payload.is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _item_to_dict(row)


@router.get("/items/{item_id}/export")
def export_item(item_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    row = db.query(Item).filter(Item.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    slug = re.sub(r"[^a-z0-9]+", "-", row.name.lower()).strip("-") or f"item-{item_id}"
    return JSONResponse(
        content=_item_to_card(row),
        headers={"Content-Disposition": f'attachment; filename="item-{slug}.json"'},
    )


@router.get("/items/export")
def export_all_items(db: Session = Depends(get_db)) -> JSONResponse:
    rows = db.query(Item).order_by(Item.id.asc()).all()
    return JSONResponse(
        content={
            "schema_version": SCHEMA_VERSION,
            "kind": "item_collection",
            "items": [_item_to_card(row) for row in rows],
        },
        headers={"Content-Disposition": 'attachment; filename="items-export.json"'},
    )


@router.post("/items/import")
def import_item(payload: ItemImportRequest, db: Session = Depends(get_db)) -> dict:
    card = payload.card
    if not isinstance(card, dict):
        raise HTTPException(status_code=422, detail="card must be a JSON object")

    name = str(card.get("name") or "").strip()[:160]
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    raw_key = str(card.get("key") or name).strip()
    key = _unique_item_key(db, raw_key)

    raw_tags = card.get("tags")
    tags = []
    if isinstance(raw_tags, list):
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()][:50]

    row = Item(
        key=key,
        name=name,
        category=str(card.get("category") or "").strip()[:80] or None,
        description=str(card.get("description") or "").strip()[:4000] or None,
        tags_json=json.dumps(tags, ensure_ascii=False),
        is_active=bool(card.get("is_active", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _item_to_dict(row)


@router.put("/items/{item_id}")
def update_item(item_id: int, payload: ItemUpdateRequest, db: Session = Depends(get_db)) -> dict:
    row = db.query(Item).filter(Item.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.key is not None:
        key = _normalise_key(payload.key)
        if not key:
            raise HTTPException(status_code=422, detail="Invalid item key")
        conflict = db.query(Item).filter(Item.key == key, Item.id != item_id).first()
        if conflict:
            raise HTTPException(status_code=409, detail=f"Item key '{key}' already exists")
        row.key = key
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.category is not None:
        row.category = payload.category.strip() or None
    if payload.description is not None:
        row.description = payload.description.strip() or None
    if payload.tags is not None:
        row.tags_json = json.dumps(payload.tags, ensure_ascii=False)
    if payload.is_active is not None:
        row.is_active = bool(payload.is_active)

    db.add(row)
    db.commit()
    db.refresh(row)
    return _item_to_dict(row)


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(Item).filter(Item.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(row)
    db.commit()
    return {"deleted": item_id}


@router.get("/scenarios/{scenario_id}/items")
def list_scenario_inventory(scenario_id: int, db: Session = Depends(get_db)) -> dict:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    rows = (
        db.query(ScenarioItem, Item)
        .join(Item, Item.id == ScenarioItem.item_id)
        .filter(ScenarioItem.scenario_id == scenario_id)
        .order_by(Item.name.asc())
        .all()
    )
    return {
        "scenario_id": scenario_id,
        "items": [_scenario_item_to_dict(link, item) for link, item in rows],
    }


@router.put("/scenarios/{scenario_id}/items")
def replace_scenario_inventory(
    scenario_id: int,
    payload: ScenarioInventoryReplaceRequest,
    db: Session = Depends(get_db),
) -> dict:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    item_ids = {entry.item_id for entry in payload.entries}
    if item_ids:
        found = db.query(Item.id).filter(Item.id.in_(item_ids)).all()
        found_ids = {row[0] for row in found}
        missing = sorted(item_ids - found_ids)
        if missing:
            raise HTTPException(status_code=404, detail=f"Unknown item ids: {missing}")

    db.query(ScenarioItem).filter(ScenarioItem.scenario_id == scenario_id).delete(synchronize_session=False)
    for entry in payload.entries:
        db.add(
            ScenarioItem(
                scenario_id=scenario_id,
                item_id=entry.item_id,
                is_required=bool(entry.is_required),
                default_quantity=entry.default_quantity,
                notes=entry.notes.strip() if entry.notes else None,
                phase_id=entry.phase_id.strip() if entry.phase_id else None,
            )
        )

    db.commit()
    return list_scenario_inventory(scenario_id=scenario_id, db=db)


@router.get("/sessions/{session_id}/items")
def list_session_inventory(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = (
        db.query(SessionItem, Item)
        .join(Item, Item.id == SessionItem.item_id)
        .filter(SessionItem.session_id == session_id)
        .order_by(Item.name.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "items": [_session_item_to_dict(link, item) for link, item in rows],
    }


@router.post("/sessions/{session_id}/items")
def add_session_item(
    session_id: int,
    payload: SessionInventoryCreateRequest,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    item = db.query(Item).filter(Item.id == payload.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.linked_scenario_item_id is not None:
        scenario_item = db.query(ScenarioItem).filter(ScenarioItem.id == payload.linked_scenario_item_id).first()
        if not scenario_item:
            raise HTTPException(status_code=404, detail="Linked scenario item not found")

    row = SessionItem(
        session_id=session_id,
        item_id=payload.item_id,
        quantity=payload.quantity,
        status=payload.status.strip(),
        is_equipped=bool(payload.is_equipped),
        notes=payload.notes.strip() if payload.notes else None,
        linked_scenario_item_id=payload.linked_scenario_item_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _session_item_to_dict(row, item)


@router.put("/sessions/{session_id}/items/{session_item_id}")
def update_session_item(
    session_id: int,
    session_item_id: int,
    payload: SessionInventoryUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    row = (
        db.query(SessionItem)
        .filter(SessionItem.id == session_item_id, SessionItem.session_id == session_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Session item not found")

    if payload.quantity is not None:
        row.quantity = payload.quantity
    if payload.status is not None:
        row.status = payload.status.strip()
    if payload.is_equipped is not None:
        row.is_equipped = bool(payload.is_equipped)
    if payload.notes is not None:
        row.notes = payload.notes.strip() or None

    db.add(row)
    db.commit()
    db.refresh(row)
    item = db.query(Item).filter(Item.id == row.item_id).first()
    if not item:
        raise HTTPException(status_code=500, detail="Corrupt session item reference")
    return _session_item_to_dict(row, item)


@router.delete("/sessions/{session_id}/items/{session_item_id}")
def delete_session_item(session_id: int, session_item_id: int, db: Session = Depends(get_db)) -> dict:
    row = (
        db.query(SessionItem)
        .filter(SessionItem.id == session_item_id, SessionItem.session_id == session_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Session item not found")
    db.delete(row)
    db.commit()
    return {"deleted": session_item_id}
