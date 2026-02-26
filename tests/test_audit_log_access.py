import json
from datetime import UTC, datetime
from uuid import uuid4

from chastease.models import AuditEntry
from tests.helpers import create_active_session, register_user


def test_audit_endpoint_hidden_by_default(client):
    auth = register_user(client, "audit-hidden")
    response = client.get(
        f"/api/v1/admin/audit/session/{uuid4()}",
        params={"auth_token": auth["auth_token"]},
    )
    assert response.status_code == 404


def test_admin_audit_entries_available_when_enabled(admin_client):
    auth = register_user(admin_client, "audit-visible")
    session_id = create_active_session(admin_client, auth)
    entry_id = str(uuid4())
    db = admin_client.app.state.db_session_factory()
    try:
        db.add(
            AuditEntry(
                id=entry_id,
                session_id=session_id,
                user_id=auth["user_id"],
                turn_id=None,
                event_type="unit_test",
                detail="audit log integration test",
                metadata_json=json.dumps({"source": "test"}),
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()

    response = admin_client.get(
        f"/api/v1/admin/audit/session/{session_id}",
        params={"auth_token": auth["auth_token"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    entries = payload.get("entries", [])
    assert any(entry.get("id") == entry_id for entry in entries)