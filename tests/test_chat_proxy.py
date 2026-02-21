def _register(client, username="chat-user", password="demo-pass-123"):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _create_active_session(client, auth):
    start = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": auth["user_id"], "auth_token": auth["auth_token"], "language": "en"},
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
