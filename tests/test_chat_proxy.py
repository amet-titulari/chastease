import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep
from uuid import uuid4

import pytest

from chastease.api.routers import chat as chat_router
from chastease.models import AuditEntry, ChastitySession


def _register(client, username="chat-user", password="demo-pass-123"):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _create_active_session(client, auth, **start_overrides):
    payload = {"user_id": auth["user_id"], "auth_token": auth["auth_token"], "language": "en"}
    payload.update(start_overrides)
    start = client.post(
        "/api/v1/setup/sessions",
        json=payload,
    )
    assert start.status_code == 200
    sid = start.json()["setup_session_id"]
    answers = client.post(
        f"/api/v1/setup/sessions/{sid}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 5},
                {"question_id": "q5_novelty_challenge", "value": 7},
                {"question_id": "q6_intensity_1_5", "value": 4},
            ]
        },
    )
    assert answers.status_code == 200
    answers_data = answers.json()

    session_id = str(uuid4())
    db = client.app.state.db_session_factory()
    try:
        db.add(
            ChastitySession(
                id=session_id,
                user_id=auth["user_id"],
                character_id=None,
                status="active",
                language=str(payload.get("language") or "en"),
                policy_snapshot_json=json.dumps(answers_data["policy_preview"]),
                psychogram_snapshot_json=json.dumps(answers_data["psychogram_preview"]),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()
    return session_id


def _update_session_snapshots(client, session_id, *, policy=None, psychogram=None):
    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        if policy is not None:
            session.policy_snapshot_json = json.dumps(policy)
        if psychogram is not None:
            session.psychogram_snapshot_json = json.dumps(psychogram)
        session.updated_at = datetime.now(UTC)
        db.add(session)
        db.commit()
    finally:
        db.close()


def test_chat_proxy_turn_and_execute_action_endpoint(client):
    auth = _register(client)
    session_id = _create_active_session(client, auth)

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Status report please.",
            "language": "en",
            "attachments": [{"name": "proof.jpg", "type": "image/jpeg", "size": 12345}],
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["result"] == "accepted"
    assert "narration" in data
    assert "pending_actions" in data

    db = client.app.state.db_session_factory()
    try:
        activity_snapshot = (
            db.query(AuditEntry)
            .filter(
                AuditEntry.session_id == session_id,
                AuditEntry.event_type == "activity_snapshot",
            )
            .order_by(AuditEntry.created_at.desc())
            .first()
        )
        assert activity_snapshot is not None
        metadata = json.loads(activity_snapshot.metadata_json or "{}")
        assert "pending_actions" in metadata
        assert "executed_actions" in metadata
        assert "failed_actions" in metadata
    finally:
        db.close()

    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "pause_timer", "payload": {"minutes": 10}},
    )
    assert execute.status_code == 200
    exec_data = execute.json()
    assert exec_data["executed"] is True
    assert exec_data["action_type"] == "pause_timer"
    assert exec_data["timer"]["state"] == "paused"
    assert exec_data["timer"]["paused_at"] is not None

    db = client.app.state.db_session_factory()
    try:
        manual_event = (
            db.query(AuditEntry)
            .filter(
                AuditEntry.session_id == session_id,
                AuditEntry.event_type == "activity_manual_execute",
            )
            .order_by(AuditEntry.created_at.desc())
            .first()
        )
        assert manual_event is not None
        metadata = json.loads(manual_event.metadata_json or "{}")
        assert metadata.get("status") == "success"
        assert metadata.get("action_type") == "pause_timer"
    finally:
        db.close()


def test_chat_turn_updates_roleplay_session_summary_and_memory(client):
    auth = _register(client, username="chat-memory-user")
    session_id = _create_active_session(client, auth)

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "I kneel, steady my breathing, and report my status.",
            "language": "en",
        },
    )
    assert turn.status_code == 200

    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        policy = json.loads(session.policy_snapshot_json)
        roleplay = policy.get("roleplay") or {}
        scene_state = roleplay.get("scene_state") or {}
        summary = roleplay.get("session_summary") or {}
        memory_entries = roleplay.get("memory_entries") or []

        assert scene_state.get("name") == "active-session"
        assert scene_state.get("phase") in {"opening", "active", "control", "reflection"}
        assert scene_state.get("beats")
        assert "summary_text" in summary
        assert "Wearer reported:" in summary["summary_text"]
        assert memory_entries
        assert any(entry.get("kind") in {"facts", "rituals", "vows", "unresolved_threads"} for entry in memory_entries)
        assert any("recent" in (entry.get("tags") or []) for entry in memory_entries)
    finally:
        db.close()

    execute_add_time = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "add_time", "payload": {"amount": 15, "unit": "minutes"}},
    )
    assert execute_add_time.status_code == 200
    assert execute_add_time.json()["action_type"] == "add_time"
    assert execute_add_time.json()["payload"]["seconds"] == 900
    end_after_add = datetime.fromisoformat(execute_add_time.json()["timer"]["effective_end_at"])

    execute_reduce_time = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "reduce_time", "payload": {"seconds": 120}},
    )
    assert execute_reduce_time.status_code == 200
    assert execute_reduce_time.json()["payload"]["seconds"] == 120
    end_after_reduce = datetime.fromisoformat(execute_reduce_time.json()["timer"]["effective_end_at"])
    assert int((end_after_add - end_after_reduce).total_seconds()) == 120

    sleep(1)
    execute_unpause = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "unpause_timer", "payload": {}},
    )
    assert execute_unpause.status_code == 200
    assert execute_unpause.json()["timer"]["state"] == "running"
    assert execute_unpause.json()["timer"]["paused_at"] is None

    session_fetch = client.get(f"/api/v1/sessions/{session_id}")
    assert session_fetch.status_code == 200
    runtime_timer = session_fetch.json()["policy"]["runtime_timer"]
    assert runtime_timer["state"] == "running"
    assert runtime_timer["remaining_seconds"] >= 0


def test_manual_action_updates_roleplay_scene_state_from_runtime(client):
    auth = _register(client, username="chat-scene-runtime-user")
    session_id = _create_active_session(client, auth)

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "I wait quietly.",
            "language": "en",
        },
    )
    assert turn.status_code == 200

    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "pause_timer", "payload": {}},
    )
    assert execute.status_code == 200
    assert execute.json()["timer"]["state"] == "paused"

    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        policy = json.loads(session.policy_snapshot_json)
        roleplay = policy.get("roleplay") or {}
        scene_state = roleplay.get("scene_state") or {}
        assert scene_state.get("phase") == "suspension"
        assert scene_state.get("status") == "paused"
        assert "timer:paused" in (scene_state.get("beats") or [])
    finally:
        db.close()


def test_hygiene_actions_update_roleplay_scene_state_from_runtime(client, monkeypatch):
    auth = _register(client, username="chat-scene-hygiene-user")
    session_id = _create_active_session(
        client,
        auth,
        integrations=["ttlock"],
        seal_mode="plomben",
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.config.TTL_CLIENT_ID = "demo-client"
    client.app.state.config.TTL_CLIENT_SECRET = "demo-secret"
    monkeypatch.setattr(chat_router, "_ttlock_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        chat_router,
        "_ttlock_command",
        lambda **_kwargs: {"errcode": 0, "errmsg": "ok", "lockId": "12345"},
    )

    open_result = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_open", "payload": {}},
    )
    assert open_result.status_code == 200

    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        policy = json.loads(session.policy_snapshot_json)
        scene_state = ((policy.get("roleplay") or {}).get("scene_state") or {})
        assert scene_state.get("phase") == "maintenance"
        assert scene_state.get("status") == "hygiene-open"
        assert "hygiene:open" in (scene_state.get("beats") or [])
        assert "action:hygiene_open" in (scene_state.get("beats") or [])
    finally:
        db.close()

    close_result = client.post(
        "/api/v1/chat/actions/execute",
        json={
            "session_id": session_id,
            "action_type": "hygiene_close",
            "payload": {"seal_text": "PLOMBE-BETA-02"},
        },
    )
    assert close_result.status_code == 200

    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        policy = json.loads(session.policy_snapshot_json)
        scene_state = ((policy.get("roleplay") or {}).get("scene_state") or {})
        assert scene_state.get("phase") == "transition"
        assert scene_state.get("status") == "resealed"
        assert "action:hygiene_close" in (scene_state.get("beats") or [])
        assert any(str(beat).startswith("seal:sealed:PLOMBE-BETA-02") for beat in (scene_state.get("beats") or []))
    finally:
        db.close()


def test_chat_add_time_respects_max_end_date_boundary(client):
    auth = _register(client, username="chat-user-max")
    session_id = _create_active_session(
        client,
        auth,
        contract_start_date="2026-01-01",
        contract_min_end_date="2026-01-01",
        contract_max_end_date="2026-01-02",
        ai_controls_end_date=False,
    )

    execute_add_time = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "add_time", "payload": {"seconds": 1}},
    )
    assert execute_add_time.status_code == 200
    timer = execute_add_time.json()["timer"]
    assert "clamped to max end date boundary" in execute_add_time.json()["message"]
    effective_end = datetime.fromisoformat(timer["effective_end_at"]).date().isoformat()
    assert effective_end == "2026-01-02"


def test_chat_reduce_time_clamps_to_min_end_date_boundary(client):
    auth = _register(client, username="chat-user-reduce-min")
    session_id = _create_active_session(
        client,
        auth,
        contract_start_date="2026-01-01",
        contract_min_end_date="2026-01-01",
        contract_max_end_date="2026-01-02",
        ai_controls_end_date=False,
    )

    execute_reduce_time = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "reduce_time", "payload": {"seconds": 86401}},
    )
    assert execute_reduce_time.status_code == 200
    timer = execute_reduce_time.json()["timer"]
    assert "clamped to min end date boundary" in execute_reduce_time.json()["message"]
    effective_end = datetime.fromisoformat(timer["effective_end_at"]).date().isoformat()
    assert effective_end == "2026-01-01"


def test_chat_unpause_respects_max_end_date_boundary(client):
    auth = _register(client, username="chat-user-unpause-max")
    session_id = _create_active_session(
        client,
        auth,
        contract_start_date="2026-01-01",
        contract_min_end_date="2026-01-01",
        contract_max_end_date="2026-01-02",
        ai_controls_end_date=False,
    )

    pause = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "pause_timer", "payload": {}},
    )
    assert pause.status_code == 200
    assert pause.json()["timer"]["state"] == "paused"

    sleep(1)
    unpause = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "unpause_timer", "payload": {}},
    )
    assert unpause.status_code == 200
    timer = unpause.json()["timer"]
    assert timer["state"] == "running"
    effective_end = datetime.fromisoformat(timer["effective_end_at"]).date().isoformat()
    assert effective_end == "2026-01-02"


def test_chat_turn_auto_executes_request_actions_in_execute_mode(client):
    auth = _register(client, username="chat-user-auto-exec")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Verstanden.\n[[REQUEST:add_time|{"amount":1,"unit":"hour","reason":"test"}]]'
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte fuege 1 Stunde hinzu.", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["pending_actions"] == []
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "add_time"
    assert data["executed_actions"][0]["payload"]["seconds"] == 3600
    assert data["failed_actions"] == []


def test_chat_turn_keeps_timer_request_actions_pending_in_suggest_mode(client):
    auth = _register(client, username="chat-user-suggest-mode")
    session_id = _create_active_session(client, auth, autonomy_mode="suggest")
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Verstanden.\n[[REQUEST:add_time|{"amount":1,"unit":"hour","reason":"test"}]]'
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte fuege 1 Stunde hinzu.", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert data["failed_actions"] == []
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "add_time"
    assert data["pending_actions"][0]["payload"] == {"seconds": 3600}


def test_chat_turn_unwraps_suggest_wrapper_in_execute_mode(client):
    auth = _register(client, username="chat-user-wrapper-exec")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Gerne.\n[[REQUEST:suggest|{"action":"add_time","duration":"1h","reason":"Tooltest"}]]'
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte fuehre aus.", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["failed_actions"] == []
    assert data["pending_actions"] == []
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "add_time"
    assert data["executed_actions"][0]["payload"] == {"seconds": 3600}


def test_chat_turn_unwraps_timer_wrapper_and_keeps_pending_in_suggest_mode(client):
    auth = _register(client, username="chat-user-wrapper-suggest")
    session_id = _create_active_session(client, auth, autonomy_mode="suggest")
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Vorschlag.\n[[REQUEST:suggest|{"action":"add_time","duration":"1h","reason":"Tooltest"}]]'
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte vorschlagen.", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert data["failed_actions"] == []
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "add_time"
    assert data["pending_actions"][0]["payload"] == {"seconds": 3600}


def test_unpause_adds_elapsed_pause_time_to_effective_end(client):
    auth = _register(client, username="chat-user-unpause-delta")
    session_id = _create_active_session(client, auth)

    pause = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "pause_timer", "payload": {}},
    )
    assert pause.status_code == 200
    end_before_pause = datetime.fromisoformat(pause.json()["timer"]["effective_end_at"])
    sleep(2)
    unpause = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "unpause_timer", "payload": {}},
    )
    assert unpause.status_code == 200
    end_after_unpause = datetime.fromisoformat(unpause.json()["timer"]["effective_end_at"])
    delta = int((end_after_unpause - end_before_pause).total_seconds())
    assert 1 <= delta <= 4


def test_pause_keeps_remaining_seconds_stable(client):
    auth = _register(client, username="chat-user-pause-stable")
    session_id = _create_active_session(client, auth)

    pause = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "pause_timer", "payload": {}},
    )
    assert pause.status_code == 200
    remaining_before = int(pause.json()["timer"]["remaining_seconds"])
    sleep(2)
    session_fetch = client.get(f"/api/v1/sessions/{session_id}")
    assert session_fetch.status_code == 200
    runtime_timer = session_fetch.json()["policy"]["runtime_timer"]
    remaining_after = int(runtime_timer["remaining_seconds"])
    assert abs(remaining_after - remaining_before) <= 1


def test_chat_turn_keeps_image_verification_as_pending_action(client):
    auth = _register(client, username="chat-user-image-pending")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Bitte sende ein Bild.\n[[REQUEST:image_verification|{"request":"Zeige das Schloss frontal.","verification_instruction":"Pruefe, ob Schloss sichtbar und geschlossen ist."}]]'
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte pruefen.", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert data["failed_actions"] == []
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "image_verification"


def test_chat_turn_keeps_hygiene_open_pending_even_in_execute_mode(client):
    auth = _register(client, username="chat-user-hygiene-pending")
    session_id = _create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Bitte bestaetigen.\n[[REQUEST:hygiene_open|{"reason":"hygiene"}]]'
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte Hygieneoeffnung.", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert data["failed_actions"] == []
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "hygiene_open"


def test_chat_turn_maps_ttlock_open_request_to_hygiene_open_pending(client):
    auth = _register(client, username="chat-user-ttlock-alias")
    session_id = _create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Bitte bestaetigen.\n[[REQUEST:ttlock_open|{"reason":"hygiene"}]]'
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte oeffnen.", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert data["failed_actions"] == []
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "hygiene_open"


def test_chat_turn_fail_closed_blocks_hygiene_fallback_when_plain_text(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = True
    auth = _register(client, username="chat-user-plain-fallback")
    session_id = _create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.ai_service.generate_narration = lambda _context: (
        "Fuer diese Hygieneoeffnung ohne Verifikation gewaehre ich eine Ausnahme. Oeffne den Kaefig."
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Kannst du eine Hygieneoeffnung ohne Verifikation starten?",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["pending_actions"] == []
    assert data["executed_actions"] == []
    assert data["action_diagnostics"]["raw_machine_tag_present"] is False
    assert data["action_diagnostics"]["reask_attempted"] is True
    assert data["action_diagnostics"]["reask_applied"] is False
    assert data["action_diagnostics"]["strict_request_tag_mode"] is True
    assert data["action_diagnostics"]["fallback_applied"] is False
    assert any("Strict request-tag mode" in str(item.get("detail", "")) for item in data["failed_actions"])


def test_chat_turn_can_use_hygiene_fallback_when_strict_mode_disabled(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = False
    auth = _register(client, username="chat-user-plain-fallback-legacy")
    session_id = _create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.ai_service.generate_narration = lambda _context: (
        "Fuer diese Hygieneoeffnung ohne Verifikation gewaehre ich eine Ausnahme. Oeffne den Kaefig."
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Kannst du eine Hygieneoeffnung ohne Verifikation starten?",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "hygiene_open"
    assert data["action_diagnostics"]["strict_request_tag_mode"] is False
    assert data["action_diagnostics"]["fallback_applied"] is True


def test_chat_turn_reask_repairs_plain_text_into_structured_request(client):
    auth = _register(client, username="chat-user-reask-repair")
    session_id = _create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    calls = {"n": 0}

    def _fake_generate(_context):
        calls["n"] += 1
        if calls["n"] == 1:
            return "Ich erlaube eine Hygieneoeffnung ohne Verifikation."
        return '[[REQUEST:hygiene_open|{"reason":"hygiene"}]]'

    client.app.state.ai_service.generate_narration = _fake_generate

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Kannst du eine Hygieneoeffnung ohne Verifikation starten?",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "hygiene_open"
    assert data["action_diagnostics"]["raw_machine_tag_present"] is False
    assert data["action_diagnostics"]["reask_attempted"] is True
    assert data["action_diagnostics"]["reask_applied"] is True
    assert data["action_diagnostics"]["fallback_applied"] is False
    assert any("repair round generated" in str(item.get("detail", "")) for item in data["failed_actions"])


def test_chat_turn_repair_keeps_image_verification_when_narration_requests_photo(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = True
    auth = _register(client, username="chat-user-repair-photo")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    calls = {"n": 0}

    def _fake_generate(_context):
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                "Kein Abzug; stattdessen verlaengere ich deinen Timer um 24 Stunden. "
                "Sende ein klares Foto von Kaefig, Schloss und Siegel zur Verifikation."
            )
        return '[[REQUEST:add_time|{"seconds":86400}]]'

    client.app.state.ai_service.generate_narration = _fake_generate

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Was soll ich machen?",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "add_time"
    assert any(action.get("action_type") == "image_verification" for action in data["pending_actions"])
    assert any(
        "added image-verification fallback" in str(item.get("detail", "")).lower()
        for item in data["failed_actions"]
    )


def test_chat_turn_falls_back_to_pause_timer_on_plain_text_intent(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = False
    auth = _register(client, username="chat-user-pause-fallback")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        "Verstanden. Freeze aktiviert. Der Timer laeuft nicht weiter."
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Kannst du bitte pausieren? Also einen freeze machen",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["pending_actions"] == []
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "pause_timer"
    assert data["action_diagnostics"]["raw_machine_tag_present"] is False
    assert data["action_diagnostics"]["strict_request_tag_mode"] is False
    assert data["action_diagnostics"]["fallback_applied"] is True


def test_chat_turn_strict_mode_allows_timer_fallback_from_ai_narration(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = True
    auth = _register(client, username="chat-user-strict-timer-fallback")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        "Ich verlaengere die Zeit jetzt um 15 Minuten und halte den Rhythmus stabil."
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Okay",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["pending_actions"] == []
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "add_time"
    assert int(data["executed_actions"][0]["payload"]["seconds"]) == 900
    assert data["action_diagnostics"]["strict_request_tag_mode"] is True
    assert data["action_diagnostics"]["fallback_applied"] is True
    assert any(
        "applied timer fallback from explicit ai narration intent" in str(item.get("detail", "")).lower()
        for item in data["failed_actions"]
    )


def test_chat_turn_prefers_ai_timer_intent_over_user_offer_in_fallback(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = False
    auth = _register(client, username="chat-user-ai-timer-preferred")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        "Ich ziehe dir keine Zeit ab; stattdessen verlaengere ich deinen Timer um 1 Tag."
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Wenn du mir jetzt 1 Tag der Zeit abziehen darfst du danach verlaengern.",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["pending_actions"] == []
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "add_time"
    assert int(data["executed_actions"][0]["payload"]["seconds"]) == 86400
    assert data["action_diagnostics"]["fallback_applied"] is True
    assert any(
        "applied timer fallback from ai narration intent" in str(item.get("detail", "")).lower()
        for item in data["failed_actions"]
    )


def test_chat_turn_strict_mode_adds_image_verification_from_plain_ai_narration(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = True
    auth = _register(client, username="chat-user-strict-image-fallback")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        "Sende mir ein klares Foto deines Kaefigs und Schlosses, damit ich den Sitz verifizieren kann."
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Okay", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "image_verification"
    assert "foto" in str(data["pending_actions"][0]["payload"].get("request", "")).lower()
    assert data["action_diagnostics"]["strict_request_tag_mode"] is True
    assert data["action_diagnostics"]["fallback_applied"] is True


def test_chat_turn_non_strict_prefers_image_verification_from_ai_narration(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = False
    auth = _register(client, username="chat-user-image-fallback")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    client.app.state.ai_service.generate_narration = lambda _context: (
        "Sende ein klares Bild von Kaefig und Siegel zur Verifikation."
    )

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Kannst du pruefen?", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert len(data["pending_actions"]) == 1
    assert data["pending_actions"][0]["action_type"] == "image_verification"
    assert data["action_diagnostics"]["fallback_applied"] is True
    assert any(
        "image-verification fallback from ai narration intent" in str(item.get("detail", "")).lower()
        for item in data["failed_actions"]
    )


def test_chat_action_execute_hygiene_open_success(client, monkeypatch):
    auth = _register(client, username="chat-user-ttlock-open")
    session_id = _create_active_session(
        client,
        auth,
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.config.TTL_CLIENT_ID = "demo-client"
    client.app.state.config.TTL_CLIENT_SECRET = "demo-secret"

    monkeypatch.setattr(chat_router, "_ttlock_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        chat_router,
        "_ttlock_command",
        lambda **_kwargs: {"errcode": 0, "errmsg": "ok", "lockId": "12345"},
    )

    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_open", "payload": {}},
    )
    assert execute.status_code == 200
    data = execute.json()
    assert data["executed"] is True
    assert data["action_type"] == "hygiene_open"
    assert data["ttlock"]["command"] == "open"
    assert data["ttlock"]["lock_id"] == "12345"
    assert data["payload"]["window_end_at"] is not None

    session_fetch = client.get(f"/api/v1/sessions/{session_id}")
    assert session_fetch.status_code == 200
    runtime_hygiene = (session_fetch.json().get("policy") or {}).get("runtime_hygiene") or {}
    assert runtime_hygiene.get("is_open") is True


def test_chat_action_execute_hygiene_close_requires_seal_text_when_enabled(client, monkeypatch):
    auth = _register(client, username="chat-user-seal-mode")
    session_id = _create_active_session(
        client,
        auth,
        integrations=["ttlock"],
        seal_mode="plomben",
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.config.TTL_CLIENT_ID = "demo-client"
    client.app.state.config.TTL_CLIENT_SECRET = "demo-secret"

    monkeypatch.setattr(chat_router, "_ttlock_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        chat_router,
        "_ttlock_command",
        lambda **_kwargs: {"errcode": 0, "errmsg": "ok", "lockId": "12345"},
    )

    open_result = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_open", "payload": {}},
    )
    assert open_result.status_code == 200
    assert open_result.json()["payload"]["seal_status"] == "broken"

    close_without_seal = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_close", "payload": {}},
    )
    assert close_without_seal.status_code == 400
    assert "Seal text is required" in str(close_without_seal.json().get("detail", ""))

    close_with_seal = client.post(
        "/api/v1/chat/actions/execute",
        json={
            "session_id": session_id,
            "action_type": "hygiene_close",
            "payload": {"seal_text": "PLOMBE-ALPHA-01"},
        },
    )
    assert close_with_seal.status_code == 200
    close_data = close_with_seal.json()
    assert close_data["payload"]["seal_status"] == "sealed"
    assert close_data["payload"]["seal_text"] == "PLOMBE-ALPHA-01"


def test_chat_action_execute_hygiene_close_requires_open_hygiene_state(client, monkeypatch):
    auth = _register(client, username="chat-user-close-no-open")
    session_id = _create_active_session(
        client,
        auth,
        integrations=["ttlock"],
        seal_mode="none",
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.config.TTL_CLIENT_ID = "demo-client"
    client.app.state.config.TTL_CLIENT_SECRET = "demo-secret"
    monkeypatch.setattr(chat_router, "_ttlock_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        chat_router,
        "_ttlock_command",
        lambda **_kwargs: {"errcode": 0, "errmsg": "ok", "lockId": "12345"},
    )

    close_without_open = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_close", "payload": {}},
    )
    assert close_without_open.status_code == 409
    assert "No active hygiene opening" in str(close_without_open.json().get("detail", ""))


def test_chat_turn_fallback_does_not_offer_hygiene_close_when_not_open(client):
    client.app.state.config.LLM_FAIL_CLOSED_REQUEST_TAG = False
    auth = _register(client, username="chat-user-fallback-close-no-open")
    session_id = _create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.ai_service.generate_narration = lambda _context: "Dann bitte Hygiene schließen."

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Bitte jetzt hygiene schliessen.",
            "language": "de",
        },
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["pending_actions"] == []
    assert data["executed_actions"] == []


def test_chat_action_execute_resolves_pending_action_by_action_id(client):
    auth = _register(client, username="chat-user-pending-resolve")
    session_id = _create_active_session(client, auth, autonomy_mode="suggest")
    now = datetime.now(UTC)
    policy = {
        "runtime_timer": {
            "state": "running",
            "effective_end_at": (now - timedelta(minutes=1)).isoformat(),
        },
        "limits": {"opening_window_minutes": 12},
    }
    _update_session_snapshots(client, session_id, policy=policy)

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Status?", "language": "de"},
    )
    assert turn.status_code == 200

    pending_before = client.get(
        f"/api/v1/chat/pending/{session_id}",
        params={"auth_token": auth["auth_token"]},
    )
    assert pending_before.status_code == 200
    pending_rows = pending_before.json()["pending_actions"]
    hygiene_open = next((item for item in pending_rows if item["action_type"] == "hygiene_open"), None)
    assert hygiene_open is not None

    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={
            "session_id": session_id,
            "action_type": "hygiene_open",
            "payload": hygiene_open["payload"],
            "action_id": hygiene_open["action_id"],
        },
    )
    assert execute.status_code == 200

    pending_after = client.get(
        f"/api/v1/chat/pending/{session_id}",
        params={"auth_token": auth["auth_token"]},
    )
    assert pending_after.status_code == 200
    assert pending_after.json()["pending_actions"] == []


def test_pending_hygiene_open_clears_after_manual_execute_without_action_id(client, monkeypatch):
    auth = _register(client, username="chat-user-pending-hygiene-clear")
    session_id = _create_active_session(
        client,
        auth,
        autonomy_mode="execute",
        integrations=["ttlock"],
        integration_config={
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_lock_id": "12345",
            }
        },
    )
    client.app.state.config.TTL_CLIENT_ID = "demo-client"
    client.app.state.config.TTL_CLIENT_SECRET = "demo-secret"
    monkeypatch.setattr(chat_router, "_ttlock_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        chat_router,
        "_ttlock_command",
        lambda **_kwargs: {"errcode": 0, "errmsg": "ok", "lockId": "12345"},
    )

    client.app.state.ai_service.generate_narration = lambda _context: (
        'Bitte bestaetigen.\n[[REQUEST:hygiene_open|{"reason":"hygiene","opening_window_minutes":15}]]'
    )
    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Bitte hygiene.", "language": "de"},
    )
    assert turn.status_code == 200
    body = turn.json()
    assert len(body["pending_actions"]) == 1
    assert body["pending_actions"][0]["action_type"] == "hygiene_open"

    before = client.get(f"/api/v1/chat/pending/{session_id}?auth_token={auth['auth_token']}")
    assert before.status_code == 200
    assert any(item.get("action_type") == "hygiene_open" for item in before.json().get("pending_actions", []))

    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_open", "payload": {}},
    )
    assert execute.status_code == 200

    after = client.get(f"/api/v1/chat/pending/{session_id}?auth_token={auth['auth_token']}")
    assert after.status_code == 200
    assert not any(item.get("action_type") == "hygiene_open" for item in after.json().get("pending_actions", []))


def test_chat_action_execute_hygiene_fails_without_integration_config(client):
    auth = _register(client, username="chat-user-ttlock-missing")
    session_id = _create_active_session(client, auth)
    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "hygiene_open", "payload": {}},
    )
    assert execute.status_code == 400
    assert "TT-Lock integration" in str(execute.json().get("detail", ""))


def test_chat_action_execute_ttlock_open_is_reserved(client):
    auth = _register(client, username="chat-user-ttlock-reserved")
    session_id = _create_active_session(client, auth)
    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "ttlock_open", "payload": {}},
    )
    assert execute.status_code == 403
    assert "not allowed for execution" in str(execute.json().get("detail", ""))


def test_chat_action_execute_freeze_alias_pauses_timer(client):
    auth = _register(client, username="chat-user-freeze-alias")
    session_id = _create_active_session(client, auth)

    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "freeze_timer", "payload": {}},
    )
    assert execute.status_code == 200
    data = execute.json()
    assert data["executed"] is True
    assert data["action_type"] == "pause_timer"
    assert data["timer"]["state"] == "paused"



def test_active_session_integrations_update_persists_to_db_policy(client):
    auth = _register(client, username="chat-user-integrations-update")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")

    update = client.post(
        f"/api/v1/sessions/{session_id}/integrations",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "integrations": ["ttlock"],
            "integration_config": {
                "ttlock": {
                    "ttl_user": "wearer@example.com",
                    "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                    "ttl_lock_id": "12345",
                }
            },
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["session_id"] == session_id
    assert body["integrations"] == ["ttlock"]
    assert body["integration_config"]["ttlock"]["ttl_lock_id"] == "12345"

    session_fetch = client.get(f"/api/v1/sessions/{session_id}")
    assert session_fetch.status_code == 200
    policy = session_fetch.json()["policy"]
    assert policy["integrations"] == ["ttlock"]
    assert policy["integration_config"]["ttlock"]["ttl_lock_id"] == "12345"


def test_chat_vision_review_saves_uploaded_image(client, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_VERIFICATION_DIR", str(tmp_path / "image_reviews"))
    auth = _register(client, username="chat-user-vision")
    session_id = _create_active_session(client, auth)

    picture_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AApMBgS9x+h0AAAAASUVORK5CYII="
    )
    review = client.post(
        "/api/v1/chat/vision-review",
        json={
            "session_id": session_id,
            "message": "Bitte pruefe dieses Bild.",
            "language": "de",
            "picture_name": "proof.png",
            "picture_content_type": "image/png",
            "picture_data_url": picture_data_url,
            "verification_instruction": "Pruefe, ob das Schloss sichtbar und geschlossen ist.",
            "verification_action_payload": {
                "request": "Zeige das Schloss frontal.",
                "verification_instruction": "Pruefe, ob das Schloss sichtbar und geschlossen ist.",
            },
            "source": "upload",
        },
    )
    assert review.status_code == 200
    data = review.json()
    assert data["result"] == "accepted"
    assert "narration" in data
    saved_path = data.get("saved_image_path")
    assert isinstance(saved_path, str) and saved_path
    assert Path(saved_path).exists()


def test_chat_vision_review_logs_failed_image_verification_activity(client, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_VERIFICATION_DIR", str(tmp_path / "image_reviews_failed"))
    auth = _register(client, username="chat-user-vision-failed")
    session_id = _create_active_session(client, auth)
    client.app.state.ai_service.generate_narration = lambda _context: "Object not compliant. Verdict: FAILED."

    picture_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AApMBgS9x+h0AAAAASUVORK5CYII="
    )
    review = client.post(
        "/api/v1/chat/vision-review",
        json={
            "session_id": session_id,
            "message": "Pruefung fuer Action Card.",
            "language": "de",
            "picture_name": "proof.png",
            "picture_content_type": "image/png",
            "picture_data_url": picture_data_url,
            "verification_action_payload": {
                "request": "Foto eines Hasen",
                "verification_instruction": "Pruefe auf echten Hasen",
            },
            "source": "upload",
        },
    )
    assert review.status_code == 200
    data = review.json()
    assert any(action.get("action_type") == "image_verification" for action in data.get("failed_actions", []))

    db = client.app.state.db_session_factory()
    try:
        activity_snapshot = (
            db.query(AuditEntry)
            .filter(
                AuditEntry.session_id == session_id,
                AuditEntry.event_type == "activity_snapshot",
            )
            .order_by(AuditEntry.created_at.desc())
            .first()
        )
        assert activity_snapshot is not None
        metadata = json.loads(activity_snapshot.metadata_json or "{}")
        failed_actions = metadata.get("failed_actions") if isinstance(metadata.get("failed_actions"), list) else []
        assert any(action.get("action_type") == "image_verification" for action in failed_actions)
    finally:
        db.close()


def test_chat_vision_review_clears_resolved_image_verification_pending(client, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_VERIFICATION_DIR", str(tmp_path / "image_reviews_resolved"))
    auth = _register(client, username=f"chat-user-vision-resolved-{uuid4().hex[:8]}")
    session_id = _create_active_session(client, auth)
    client.app.state.ai_service.generate_narration = lambda _context: (
        'Pruefung abgeschlossen. Verdict: PASSED.\n'
        '[[REQUEST:image_verification|{"request":"Foto eines Hasen","verification_instruction":"Pruefe auf echten Hasen"}]]'
    )

    picture_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AApMBgS9x+h0AAAAASUVORK5CYII="
    )
    review = client.post(
        "/api/v1/chat/vision-review",
        json={
            "session_id": session_id,
            "message": "Pruefung fuer Action Card.",
            "language": "de",
            "picture_name": "proof.png",
            "picture_content_type": "image/png",
            "picture_data_url": picture_data_url,
            "verification_action_payload": {
                "request": "Foto eines Hasen",
                "verification_instruction": "Pruefe auf echten Hasen",
            },
            "source": "upload",
        },
    )
    assert review.status_code == 200
    data = review.json()
    assert data["pending_actions"] == []
    assert any(action.get("action_type") == "image_verification" for action in data.get("executed_actions", []))

    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        policy = json.loads(session.policy_snapshot_json or "{}")
        scene_state = ((policy.get("roleplay") or {}).get("scene_state") or {})
        assert "verification:passed" in (scene_state.get("beats") or [])
    finally:
        db.close()


def test_chat_turn_history_endpoint_returns_persisted_turns(client):
    auth = _register(client, username="chat-user-history")
    session_id = _create_active_session(client, auth)

    turn = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Bitte gib mir ein kurzes Status-Update.",
            "language": "de",
            "attachments": [],
        },
    )
    assert turn.status_code == 200

    turns = client.get(f"/api/v1/sessions/{session_id}/turns")
    assert turns.status_code == 200
    data = turns.json()
    assert data["session_id"] == session_id
    assert isinstance(data["turns"], list)
    assert len(data["turns"]) >= 1
    last_turn = data["turns"][-1]
    assert "player_action" in last_turn
    assert "ai_narration" in last_turn


def test_chat_turn_safeword_abort_requires_two_confirmations_and_reason(client):
    auth = _register(client, username="chat-user-abort-flow")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    psychogram = {
        "safety_profile": {
            "mode": "safeword",
            "safeword": "stopp",
            "safeword_abort_protocol": {
                "confirmation_questions_required": 2,
                "reason_required": True,
            },
        }
    }
    _update_session_snapshots(client, session_id, psychogram=psychogram)

    trigger = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Stopp", "language": "de"},
    )
    assert trigger.status_code == 200
    assert len(trigger.json()["pending_actions"]) == 1
    assert trigger.json()["pending_actions"][0]["action_type"] == "abort_decision"

    first_confirmation = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Ich bestaetige den Abbruch", "language": "de"},
    )
    assert first_confirmation.status_code == 200
    assert len(first_confirmation.json()["pending_actions"]) == 1
    assert first_confirmation.json()["pending_actions"][0]["action_type"] == "abort_decision"

    second_with_reason = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Grund: Schmerzen am Schloss", "language": "de"},
    )
    assert second_with_reason.status_code == 200
    data = second_with_reason.json()
    assert len(data["failed_actions"]) == 1
    failed_action = data["failed_actions"][0]
    assert failed_action["action_type"] == "ttlock_open"
    assert failed_action["detail"] == "TT-Lock integration is not enabled in this session policy."
    assert failed_action["payload"].get("reason") == "Grund: Schmerzen am Schloss"
    assert failed_action["payload"].get("emergency") is True
    assert data["pending_actions"] == []

    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        policy = json.loads(session.policy_snapshot_json)
        scene_state = ((policy.get("roleplay") or {}).get("scene_state") or {})
        assert scene_state.get("phase") == "emergency"
        assert scene_state.get("status") == "abort-blocked"
        assert "abort:failed-open" in (scene_state.get("beats") or [])
        assert "failed:ttlock_open" in (scene_state.get("beats") or [])
    finally:
        db.close()


def test_chat_turn_abort_can_be_cancelled_with_reason(client):
    auth = _register(client, username="chat-user-abort-cancel")
    session_id = _create_active_session(client, auth, autonomy_mode="execute")
    psychogram = {
        "safety_profile": {
            "mode": "traffic_light",
            "traffic_light_words": {"green": "gruen", "yellow": "gelb", "red": "rot"},
            "red_abort_protocol": {
                "confirmation_questions_required": 2,
                "reason_required": True,
            },
        }
    }
    _update_session_snapshots(client, session_id, psychogram=psychogram)

    trigger = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "ROT", "language": "de"},
    )
    assert trigger.status_code == 200
    assert len(trigger.json()["pending_actions"]) == 1
    assert trigger.json()["pending_actions"][0]["action_type"] == "abort_decision"

    cancel = client.post(
        "/api/v1/chat/turn",
        json={
            "session_id": session_id,
            "message": "Nicht abbrechen. Es geht nicht um mich. Keine akute Gefahr. Grund: Kontext war extern.",
            "language": "de",
        },
    )
    assert cancel.status_code == 200
    data = cancel.json()
    assert data["pending_actions"] == []
    assert data["failed_actions"] == []


def test_chat_turn_timer_expiry_creates_hygiene_open_pending(client):
    auth = _register(client, username="chat-user-expired-timer")
    session_id = _create_active_session(client, auth, autonomy_mode="suggest")
    now = datetime.now(UTC)
    policy = {
        "runtime_timer": {
            "state": "running",
            "effective_end_at": (now - timedelta(minutes=1)).isoformat(),
        },
        "limits": {"opening_window_minutes": 12},
    }
    _update_session_snapshots(client, session_id, policy=policy)

    turn = client.post(
        "/api/v1/chat/turn",
        json={"session_id": session_id, "message": "Status?", "language": "de"},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["executed_actions"] == []
    assert data["failed_actions"] == []
    assert len(data["pending_actions"]) >= 1
    hygiene_pending = [item for item in data["pending_actions"] if item.get("action_type") == "hygiene_open"]
    assert len(hygiene_pending) == 1
    assert hygiene_pending[0]["payload"]["trigger"] == "timer_expired"
    assert hygiene_pending[0]["payload"]["opening_window_minutes"] == 12

    db = client.app.state.db_session_factory()
    try:
        session = db.get(ChastitySession, session_id)
        assert session is not None
        policy = json.loads(session.policy_snapshot_json)
        scene_state = ((policy.get("roleplay") or {}).get("scene_state") or {})
        assert scene_state.get("phase") == "transition"
        assert scene_state.get("status") == "timer-expired"
        assert "timer:expired" in (scene_state.get("beats") or [])
    finally:
        db.close()
