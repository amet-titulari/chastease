import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from chastease.models import AuditEntry


def record_audit_event(
    db: Session,
    session_id: str,
    user_id: str,
    event_type: str,
    detail: str,
    metadata: dict | None = None,
    turn_id: str | None = None,
) -> None:
    entry = AuditEntry(
        id=str(uuid4()),
        session_id=session_id,
        user_id=user_id,
        turn_id=turn_id,
        event_type=str(event_type or "").strip(),
        detail=str(detail or "").strip(),
        metadata_json=json.dumps(metadata or {}),
        created_at=datetime.now(UTC),
    )
    db.add(entry)
