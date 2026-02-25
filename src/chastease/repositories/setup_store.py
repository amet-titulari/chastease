import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from sqlalchemy import create_engine, text

_LOCK = Lock()
_STORE_KEY = "setup_sessions"


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///data/chastease.db")


@lru_cache(maxsize=4)
def _engine_for(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def _store_path() -> Path:
    raw_path = os.getenv("SETUP_STORE_PATH", "data/setup_sessions.json")
    return Path(raw_path)


def _read_legacy_file_sessions() -> dict[str, dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8").strip()
    except Exception:
        return {}
    if not content:
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ensure_store_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS setup_sessions_store (
                store_key VARCHAR(64) PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )


def _bootstrap_from_legacy_file_if_needed(conn) -> None:
    existing = conn.execute(
        text("SELECT payload_json FROM setup_sessions_store WHERE store_key = :key"),
        {"key": _STORE_KEY},
    ).scalar_one_or_none()
    if existing is not None:
        return
    legacy = _read_legacy_file_sessions()
    payload = json.dumps(legacy)
    now = datetime.now(UTC)
    conn.execute(
        text(
            "INSERT INTO setup_sessions_store (store_key, payload_json, updated_at) "
            "VALUES (:key, :payload_json, :updated_at)"
        ),
        {"key": _STORE_KEY, "payload_json": payload, "updated_at": now},
    )


def load_sessions() -> dict[str, dict[str, Any]]:
    with _LOCK:
        engine = _engine_for(_database_url())
        with engine.begin() as conn:
            _ensure_store_table(conn)
            _bootstrap_from_legacy_file_if_needed(conn)
            payload_json = conn.execute(
                text("SELECT payload_json FROM setup_sessions_store WHERE store_key = :key"),
                {"key": _STORE_KEY},
            ).scalar_one_or_none()
        if not payload_json:
            return {}
        try:
            parsed = json.loads(str(payload_json))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


def save_sessions(sessions: dict[str, dict[str, Any]]) -> None:
    with _LOCK:
        engine = _engine_for(_database_url())
        payload_json = json.dumps(sessions)
        now = datetime.now(UTC)
        with engine.begin() as conn:
            _ensure_store_table(conn)
            _bootstrap_from_legacy_file_if_needed(conn)
            updated = conn.execute(
                text(
                    "UPDATE setup_sessions_store "
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
                        "INSERT INTO setup_sessions_store (store_key, payload_json, updated_at) "
                        "VALUES (:key, :payload_json, :updated_at)"
                    ),
                    {
                        "key": _STORE_KEY,
                        "payload_json": payload_json,
                        "updated_at": now,
                    },
                )
