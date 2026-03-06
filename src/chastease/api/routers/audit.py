import json
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select

from chastease.api.runtime import get_db_session, resolve_user_id_from_token
from chastease.models import AuditEntry, ChastitySession, Turn

router = APIRouter(prefix="/admin", tags=["admin"])


def _load_entry_metadata(entry: AuditEntry) -> dict:
    metadata = {}
    if entry.metadata_json:
        try:
            metadata = json.loads(entry.metadata_json)
        except Exception:
            metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def _activity_key(action_type: str, payload: dict) -> tuple[str, str]:
    normalized_action = str(action_type or "").strip().lower()
    normalized_payload = payload if isinstance(payload, dict) else {}
    try:
        payload_key = json.dumps(normalized_payload, sort_keys=True, ensure_ascii=True)
    except Exception:
        payload_key = "{}"
    return normalized_action, payload_key


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
            select(AuditEntry)
            .where(AuditEntry.session_id == session_id)
            .order_by(desc(AuditEntry.created_at))
        ).all()
        payload = []
        for entry in entries:
            metadata = _load_entry_metadata(entry)
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


@router.get("/activity/session/{session_id}")
def list_activity_entries(session_id: str, auth_token: str, request: Request) -> dict:
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

        turns = db.scalars(
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(desc(Turn.turn_no))
        ).all()
        turn_map = {turn.id: turn for turn in turns}

        activity_events = db.scalars(
            select(AuditEntry)
            .where(
                AuditEntry.session_id == session_id,
                AuditEntry.event_type.in_(["activity_snapshot", "activity_manual_execute"]),
            )
            .order_by(desc(AuditEntry.created_at))
        ).all()

        activity_rows: list[dict] = []
        resolved_keys: set[tuple[str, str]] = set()
        for event in activity_events:
            metadata = _load_entry_metadata(event)
            if event.event_type == "activity_manual_execute":
                action_type = str(metadata.get("action_type") or "")
                payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
                status = str(metadata.get("status") or "success")
                if status in {"success", "failed"}:
                    resolved_keys.add(_activity_key(action_type, payload))
                activity_rows.append(
                    {
                        "event_id": event.id,
                        "turn_id": None,
                        "turn_no": None,
                        "source": "manual_execute",
                        "status": status,
                        "action_type": action_type,
                        "payload": payload,
                        "detail": str(metadata.get("message") or event.detail or ""),
                        "created_at": event.created_at.isoformat(),
                    }
                )
                continue

            turn = turn_map.get(event.turn_id) if event.turn_id else None
            pending_actions = metadata.get("pending_actions") if isinstance(metadata.get("pending_actions"), list) else []
            executed_actions = (
                metadata.get("executed_actions") if isinstance(metadata.get("executed_actions"), list) else []
            )
            failed_actions = metadata.get("failed_actions") if isinstance(metadata.get("failed_actions"), list) else []

            for action in executed_actions:
                payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
                action_type = str(action.get("action_type") or "")
                resolved_keys.add(_activity_key(action_type, payload))
                activity_rows.append(
                    {
                        "event_id": event.id,
                        "turn_id": event.turn_id,
                        "turn_no": turn.turn_no if turn else None,
                        "source": "turn",
                        "status": "success",
                        "action_type": action_type,
                        "payload": payload,
                        "detail": str(action.get("message") or "Action executed."),
                        "created_at": event.created_at.isoformat(),
                    }
                )

            for action in failed_actions:
                payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
                action_type = str(action.get("action_type") or "")
                resolved_keys.add(_activity_key(action_type, payload))
                activity_rows.append(
                    {
                        "event_id": event.id,
                        "turn_id": event.turn_id,
                        "turn_no": turn.turn_no if turn else None,
                        "source": "turn",
                        "status": "failed",
                        "action_type": action_type,
                        "payload": payload,
                        "detail": str(action.get("detail") or "Action failed."),
                        "created_at": event.created_at.isoformat(),
                    }
                )

            for action in pending_actions:
                payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
                action_type = str(action.get("action_type") or "")
                if _activity_key(action_type, payload) in resolved_keys:
                    continue
                activity_rows.append(
                    {
                        "event_id": event.id,
                        "turn_id": event.turn_id,
                        "turn_no": turn.turn_no if turn else None,
                        "source": "turn",
                        "status": "pending",
                        "action_type": action_type,
                        "payload": payload,
                        "detail": "Waiting for execute confirmation.",
                        "created_at": event.created_at.isoformat(),
                    }
                )

        return {
            "session_id": session_id,
            "total": len(activity_rows),
            "activities": activity_rows,
        }
    finally:
        db.close()
