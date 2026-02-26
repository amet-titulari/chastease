import json
from datetime import UTC, datetime, timedelta

from chastease.api.routers import chat as chat_router
from tests.helpers import create_active_session, register_user, update_session_snapshots


def test_emergency_abort_executes_ttlock_open_and_archives_session(client, monkeypatch):
    auth = register_user(client, "emerg-user")
    session_id = create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "lock-123",
            }
        },
    )

    # Configure safeword abort protocol
    psychogram = {
        "safety_profile": {
            "mode": "safeword",
            "safeword": "stopp",
            "safeword_abort_protocol": {"confirmation_questions_required": 2, "reason_required": True},
        }
    }
    update_session_snapshots(client, session_id, psychogram=psychogram)

    # Monkeypatch TTLock calls to simulate success
    monkeypatch.setattr(chat_router, "_ttlock_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(chat_router, "_ttlock_command", lambda **_kwargs: {"errcode": 0, "errmsg": "ok", "lockId": "lock-123"})

    # Trigger abort flow
    r1 = client.post("/api/v1/chat/turn", json={"session_id": session_id, "message": "stopp", "language": "de"})
    assert r1.status_code == 200

    r2 = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Ich bestaetige den Abbruch", "language": "de"},
    )
    assert r2.status_code == 200

    r3 = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Grund: Schmerzen am Schloss", "language": "de"},
    )
    assert r3.status_code == 200
    data = r3.json()

    # Expect ttlock_open executed as emergency and session archived
    executed = data.get("executed_actions") or []
    assert any(str(a.get("action_type") or "").lower() == "ttlock_open" for a in executed)

    session_fetch = client.get(f"/api/v1/sessions/{session_id}")
    assert session_fetch.status_code == 200
    assert session_fetch.json()["status"] == "archived"


def test_opening_limit_blocks_non_emergency_open(client):
    auth = register_user(client, "limit-user")
    session_id = create_active_session(client, auth, autonomy_mode="execute")

    now = datetime.now(UTC)
    policy = {
        "limits": {"opening_limit_period": "day", "max_openings_in_period": 1},
        "runtime_opening_limits": {"open_events": [now.isoformat()]},
    }
    update_session_snapshots(client, session_id, policy=policy)

    # Attempt non-emergency hygiene open should be blocked (400 or 409)
    resp = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_open", "payload": {"trigger": "user_request"}},
    )
    assert resp.status_code in (400, 409)
