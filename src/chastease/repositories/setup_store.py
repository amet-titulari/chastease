import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

_LOCK = Lock()


def _store_path() -> Path:
    raw_path = os.getenv("SETUP_STORE_PATH", "data/setup_sessions.json")
    return Path(raw_path)


def _ensure_store_file() -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}", encoding="utf-8")


def load_sessions() -> dict[str, dict[str, Any]]:
    with _LOCK:
        _ensure_store_file()
        path = _store_path()
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {}
        if isinstance(data, dict):
            return data
        return {}


def save_sessions(sessions: dict[str, dict[str, Any]]) -> None:
    with _LOCK:
        _ensure_store_file()
        path = _store_path()
        path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
