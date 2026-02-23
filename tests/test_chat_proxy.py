from datetime import datetime
from pathlib import Path
from time import sleep

from chastease.api.routers import chat as chat_router


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
    sid = start.json()["setup_session_id"]
    client.post(
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
    complete = client.post(f"/api/v1/setup/sessions/{sid}/complete")
    return complete.json()["chastity_session"]["session_id"]


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
    effective_end = datetime.fromisoformat(timer["effective_end_at"]).date().isoformat()
    assert effective_end == "2026-01-02"


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


def test_chat_turn_auto_executes_timer_request_actions_in_suggest_mode(client):
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
    assert data["pending_actions"] == []
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "add_time"
    assert data["executed_actions"][0]["payload"] == {"seconds": 3600}


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


def test_chat_turn_unwraps_and_executes_timer_wrapper_in_suggest_mode(client):
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
    assert len(data["executed_actions"]) == 1
    assert data["executed_actions"][0]["action_type"] == "add_time"
    assert data["executed_actions"][0]["payload"] == {"seconds": 3600}
    assert data["failed_actions"] == []
    assert data["pending_actions"] == []


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


def test_chat_action_execute_ttlock_open_success(client, monkeypatch):
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
        json={"session_id": session_id, "action_type": "ttlock_open", "payload": {}},
    )
    assert execute.status_code == 200
    data = execute.json()
    assert data["executed"] is True
    assert data["action_type"] == "ttlock_open"
    assert data["ttlock"]["command"] == "open"
    assert data["ttlock"]["lock_id"] == "12345"


def test_chat_action_execute_ttlock_fails_without_integration_config(client):
    auth = _register(client, username="chat-user-ttlock-missing")
    session_id = _create_active_session(client, auth)
    execute = client.post(
        "/api/v1/chat/actions/execute",
        json={"session_id": session_id, "action_type": "ttlock_open", "payload": {}},
    )
    assert execute.status_code == 400
    assert "TT-Lock integration" in str(execute.json().get("detail", ""))


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
