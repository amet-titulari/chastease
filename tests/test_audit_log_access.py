import json
from datetime import UTC, datetime, timedelta
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


def test_activity_endpoint_hidden_by_default(client):
    auth = register_user(client, "activity-hidden")
    response = client.get(
        f"/api/v1/admin/activity/session/{uuid4()}",
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


def test_admin_activity_entries_available_when_enabled(admin_client):
    auth = register_user(admin_client, "activity-visible")
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
                event_type="activity_manual_execute",
                detail="manual action test",
                metadata_json=json.dumps(
                    {
                        "status": "success",
                        "action_type": "pause_timer",
                        "payload": {"seconds": 60},
                        "message": "ok",
                    }
                ),
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()

    response = admin_client.get(
        f"/api/v1/admin/activity/session/{session_id}",
        params={"auth_token": auth["auth_token"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    activities = payload.get("activities", [])
    assert any(item.get("event_id") == entry_id for item in activities)


def test_admin_activity_hides_stale_pending_when_failed_exists(admin_client):
    auth = register_user(admin_client, "activity-dedupe")
    session_id = create_active_session(admin_client, auth)
    payload = {
        "request": "Foto eines Hasen",
        "verification_instruction": "Pruefe auf echten Hasen",
    }
    now = datetime.now(UTC)
    older_event_id = str(uuid4())
    newer_event_id = str(uuid4())

    db = admin_client.app.state.db_session_factory()
    try:
        db.add(
            AuditEntry(
                id=older_event_id,
                session_id=session_id,
                user_id=auth["user_id"],
                turn_id=None,
                event_type="activity_snapshot",
                detail="older pending snapshot",
                metadata_json=json.dumps(
                    {
                        "pending_actions": [{"action_type": "image_verification", "payload": payload}],
                        "executed_actions": [],
                        "failed_actions": [],
                    }
                ),
                created_at=now - timedelta(seconds=10),
            )
        )
        db.add(
            AuditEntry(
                id=newer_event_id,
                session_id=session_id,
                user_id=auth["user_id"],
                turn_id=None,
                event_type="activity_snapshot",
                detail="newer failed snapshot",
                metadata_json=json.dumps(
                    {
                        "pending_actions": [],
                        "executed_actions": [],
                        "failed_actions": [
                            {
                                "action_type": "image_verification",
                                "payload": payload,
                                "detail": "Image verification verdict: FAILED.",
                            }
                        ],
                    }
                ),
                created_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    response = admin_client.get(
        f"/api/v1/admin/activity/session/{session_id}",
        params={"auth_token": auth["auth_token"]},
    )
    assert response.status_code == 200
    activities = response.json().get("activities", [])
    failed_rows = [
        item
        for item in activities
        if item.get("action_type") == "image_verification" and item.get("status") == "failed"
    ]
    pending_rows = [
        item
        for item in activities
        if item.get("action_type") == "image_verification" and item.get("status") == "pending"
    ]
    assert len(failed_rows) == 1
    assert pending_rows == []