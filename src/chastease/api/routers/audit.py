import json
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from chastease.api.runtime import get_db_session, resolve_user_id_from_token
from chastease.models import AuditEntry, ChastitySession

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit/session/{session_id}")
def list_audit_entries(session_id: str, auth_token: str, request: Request) -> dict:
    if not getattr(request.app.state.config, "ENABLE_AUDIT_LOG_VIEW", False):
        raise HTTPException(status_code=404, detail="Not found.")

    user_id = resolve_user_id_from_token(auth_token, request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid auth token.")

    db = get_db_session(request)
    try:
        session = db.get(ChastitySession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chastity session not found.")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user.")

        entries = db.scalars(
            select(AuditEntry).where(AuditEntry.session_id == session_id).order_by(AuditEntry.created_at)
        ).all()
        payload = []
        for entry in entries:
            metadata = {}
            if entry.metadata_json:
                try:
                    metadata = json.loads(entry.metadata_json)
                except Exception:
                    metadata = {}
            payload.append(
                {
                    "id": entry.id,
                    "event_type": entry.event_type,
                    "detail": entry.detail,
                    "metadata": metadata,
                    "created_at": entry.created_at.isoformat(),
                }
            )
        return {"session_id": session_id, "entries": payload}
    finally:
        db.close()
