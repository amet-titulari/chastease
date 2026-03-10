"""Audit logger — writes JSON-lines to a file when CHASTEASE_AUDIT_LOG_ENABLED=true."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


def audit_log(event: str, session_id: int | None = None, **kwargs: Any) -> None:
    """Append a structured audit entry. Silently no-ops when audit log is disabled."""
    if not settings.audit_log_enabled:
        return
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "session_id": session_id,
        **kwargs,
    }
    try:
        path = Path(settings.audit_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # audit failure must never break the application
