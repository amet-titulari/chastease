from datetime import datetime
from time import sleep


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
    assert execute_add_time.status_code == 400
    assert "max_end_date boundary" in execute_add_time.json()["detail"]


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
    assert unpause.status_code == 400
    assert "max_end_date boundary" in unpause.json()["detail"]
