import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock
from typing import Any, Literal

from sqlalchemy import create_engine, text

_LOCK = Lock()
_STORE_KEY = "roleplay_assets"
_AssetKind = Literal["characters", "scenarios"]


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///data/chastease.db")


@lru_cache(maxsize=4)
def _engine_for(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def _ensure_store_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS roleplay_assets_store (
                store_key VARCHAR(64) PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )


def load_roleplay_assets() -> dict[str, Any]:
    with _LOCK:
        db_url = _database_url()
        engine = _engine_for(db_url)
        with engine.begin() as conn:
            _ensure_store_table(conn)
            payload_json = conn.execute(
                text("SELECT payload_json FROM roleplay_assets_store WHERE store_key = :key"),
                {"key": _STORE_KEY},
            ).scalar_one_or_none()
        if not payload_json:
            return {"users": {}}
        try:
            parsed = json.loads(str(payload_json))
        except json.JSONDecodeError:
            return {"users": {}}
        if not isinstance(parsed, dict):
            return {"users": {}}
        parsed.setdefault("users", {})
        return parsed


def save_roleplay_assets(payload: dict[str, Any]) -> None:
    with _LOCK:
        db_url = _database_url()
        engine = _engine_for(db_url)
        now = datetime.now(UTC)
        payload_json = json.dumps(payload)
        with engine.begin() as conn:
            _ensure_store_table(conn)
            updated = conn.execute(
                text(
                    "UPDATE roleplay_assets_store "
                    "SET payload_json = :payload_json, updated_at = :updated_at "
                    "WHERE store_key = :key"
                ),
                {
                    "key": _STORE_KEY,
                    "payload_json": payload_json,
                    "updated_at": now,
                },
            )
            if int(getattr(updated, "rowcount", 0) or 0) == 0:
                conn.execute(
                    text(
                        "INSERT INTO roleplay_assets_store (store_key, payload_json, updated_at) "
                        "VALUES (:key, :payload_json, :updated_at)"
                    ),
                    {
                        "key": _STORE_KEY,
                        "payload_json": payload_json,
                        "updated_at": now,
                    },
                )


def _ensure_user_bucket(store: dict[str, Any], user_id: str) -> dict[str, Any]:
    users = store.setdefault("users", {})
    user_bucket = users.setdefault(user_id, {})
    user_bucket.setdefault("characters", {})
    user_bucket.setdefault("scenarios", {})
    return user_bucket


def list_user_roleplay_assets(user_id: str, kind: _AssetKind) -> list[dict[str, Any]]:
    store = load_roleplay_assets()
    user_bucket = ((store.get("users") or {}).get(user_id) or {})
    items = user_bucket.get(kind) or {}
    if not isinstance(items, dict):
        return []
    label_field = "display_name" if kind == "characters" else "title"
    return sorted(
        [value for value in items.values() if isinstance(value, dict)],
        key=lambda item: (
            str(item.get("updated_at") or ""),
            str(item.get(label_field) or item.get("asset_id") or "").lower(),
        ),
        reverse=True,
    )


def get_user_roleplay_asset(user_id: str, kind: _AssetKind, asset_id: str | None) -> dict[str, Any] | None:
    normalized_id = str(asset_id or "").strip()
    if not normalized_id:
        return None
    store = load_roleplay_assets()
    user_bucket = ((store.get("users") or {}).get(user_id) or {})
    items = user_bucket.get(kind) or {}
    if not isinstance(items, dict):
        return None
    asset = items.get(normalized_id)
    return asset if isinstance(asset, dict) else None


def upsert_user_roleplay_asset(user_id: str, kind: _AssetKind, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_id = str(asset_id or "").strip()
    if not normalized_id:
        raise ValueError("asset_id is required")
    store = load_roleplay_assets()
    user_bucket = _ensure_user_bucket(store, user_id)
    items = user_bucket[kind]
    existing = items.get(normalized_id) if isinstance(items.get(normalized_id), dict) else {}
    now_iso = datetime.now(UTC).isoformat()
    record = {
        **existing,
        **payload,
        "asset_id": normalized_id,
        "user_id": user_id,
        "created_at": existing.get("created_at") or now_iso,
        "updated_at": now_iso,
    }
    items[normalized_id] = record
    save_roleplay_assets(store)
    return record


def delete_user_roleplay_asset(user_id: str, kind: _AssetKind, asset_id: str | None) -> bool:
    normalized_id = str(asset_id or "").strip()
    if not normalized_id:
        return False
    store = load_roleplay_assets()
    user_bucket = ((store.get("users") or {}).get(user_id) or {})
    items = user_bucket.get(kind) or {}
    if not isinstance(items, dict) or normalized_id not in items:
        return False
    del items[normalized_id]
    save_roleplay_assets(store)
    return True