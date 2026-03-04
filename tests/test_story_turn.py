import time


def _register_and_complete_setup(client, username="story-user", email=None):
    auth_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "display_name": username,
            "password": "demo-pass-123",
        },
    )
    assert auth_response.status_code == 200
    user_id = auth_response.json()["user_id"]
    auth_token = auth_response.json()["auth_token"]
    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth_token, "language": "en"},
    )
    assert setup_response.status_code == 200
    setup_id = setup_response.json()["setup_session_id"]

    client.post(
        f"/api/v1/setup/sessions/{setup_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 5},
                {"question_id": "q5_novelty_challenge", "value": 7},
                {"question_id": "q6_intensity_1_5", "value": 4},
                {"question_id": "q8_instruction_style", "value": "mixed"},
                {"question_id": "q9_open_context", "value": "Ready."},
            ]
        },
    )
    complete_response = client.post(f"/api/v1/setup/sessions/{setup_id}/complete")
    assert complete_response.status_code == 200
    session_id = complete_response.json()["chastity_session"]["session_id"]
    return session_id


def test_story_turn_requires_action(client):
    response = client.post("/api/v1/story/turn", json={"session_id": "missing"})
    assert response.status_code == 422


def test_story_turn_requires_session_id(client):
    response = client.post("/api/v1/story/turn", json={"action": "Ich oeffne die Truhe."})
    assert response.status_code == 400


def test_story_turn_unknown_session_returns_404(client):
    response = client.post(
        "/api/v1/story/turn",
        json={"session_id": "00000000-0000-0000-0000-000000000000", "action": "I act."},
    )
    assert response.status_code == 404


def test_story_turn_returns_job_accepted(client):
    session_id = _register_and_complete_setup(client, "story-job-user")
    response = client.post(
        "/api/v1/story/turn",
        json={"session_id": session_id, "action": "I follow the instruction.", "language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "accepted"
    assert data["status"] == "pending"
    assert "job_id" in data
    assert data["session_id"] == session_id


def test_story_turn_job_poll_pending_then_done(client):
    session_id = _register_and_complete_setup(client, "story-poll-user")
    turn_response = client.post(
        "/api/v1/story/turn",
        json={"session_id": session_id, "action": "I follow the instruction.", "language": "en"},
    )
    assert turn_response.status_code == 200
    job_id = turn_response.json()["job_id"]

    for _ in range(20):
        poll = client.get(f"/api/v1/story/turn/job/{job_id}")
        assert poll.status_code == 200
        if poll.json()["status"] != "pending":
            break
        time.sleep(0.2)

    poll_data = poll.json()
    assert poll_data["job_id"] == job_id
    assert poll_data["session_id"] == session_id
    assert poll_data["status"] in ("done", "error")


def test_story_turn_job_poll_unknown_returns_404(client):
    response = client.get("/api/v1/story/turn/job/nonexistent-job-id")
    assert response.status_code == 404


def test_story_turn_persistent_flow(client):
    session_id = _register_and_complete_setup(client, "story-flow-user")

    response1 = client.post(
        "/api/v1/story/turn",
        json={"session_id": session_id, "action": "I follow the instruction.", "language": "en"},
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["result"] == "accepted"
    assert "job_id" in data1

    response2 = client.post(
        "/api/v1/story/turn",
        json={"session_id": session_id, "action": "I report back.", "language": "en"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["result"] == "accepted"
    assert "job_id" in data2

    turns_response = client.get(f"/api/v1/sessions/{session_id}/turns")
    assert turns_response.status_code == 200
