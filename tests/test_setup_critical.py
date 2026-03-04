def _register(client, username, password="demo-pass-123"):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _start_setup(client, auth, language="en"):
    response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": auth["user_id"], "auth_token": auth["auth_token"], "language": language},
    )
    assert response.status_code == 200
    return response.json()


_FULL_ANSWERS = [
    {"question_id": "q1_rule_structure", "value": 8},
    {"question_id": "q2_strictness_authority", "value": 7},
    {"question_id": "q3_control_need", "value": 8},
    {"question_id": "q4_praise_importance", "value": 5},
    {"question_id": "q5_novelty_challenge", "value": 7},
    {"question_id": "q6_intensity_1_5", "value": 4},
    {"question_id": "q8_instruction_style", "value": "mixed"},
    {"question_id": "q9_open_context", "value": "Ready."},
]


def test_setup_start_returns_questions(client):
    auth = _register(client, "setup-q-user")
    data = _start_setup(client, auth)
    assert data["status"] == "setup_in_progress"
    assert len(data["questions"]) > 0
    assert data["language"] == "en"


def test_setup_start_requires_valid_auth_token(client):
    response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": "nonexistent-id", "auth_token": "bad-token-xyz"},
    )
    assert response.status_code == 401


def test_setup_answers_updates_previews(client):
    auth = _register(client, "setup-ans-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    response = client.post(
        f"/api/v1/setup/sessions/{sid}/answers",
        json={"answers": _FULL_ANSWERS},
    )
    assert response.status_code == 200
    data = response.json()
    assert "psychogram_preview" in data
    assert "policy_preview" in data
    assert data["answered_questions"] >= 8


def test_setup_complete_creates_active_session(client):
    auth = _register(client, "setup-complete-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    client.post(f"/api/v1/setup/sessions/{sid}/answers", json={"answers": _FULL_ANSWERS})
    response = client.post(f"/api/v1/setup/sessions/{sid}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "configured"
    assert data["chastity_session"]["status"] == "active"
    assert data["chastity_session"]["user_id"] == auth["user_id"]


def test_setup_complete_requires_min_answers(client):
    auth = _register(client, "setup-min-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    response = client.post(f"/api/v1/setup/sessions/{sid}/complete")
    assert response.status_code == 400


def test_setup_get_returns_session_state(client):
    auth = _register(client, "setup-get-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    response = client.get(f"/api/v1/setup/sessions/{sid}")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == auth["user_id"]
    assert data["status"] == "setup_in_progress"
    assert data["language"] == "en"


def test_setup_get_unknown_session_returns_404(client):
    response = client.get("/api/v1/setup/sessions/nonexistent-session-id")
    assert response.status_code == 404


def test_setup_complete_produces_psychogram_analysis(client):
    auth = _register(client, "setup-psych-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    client.post(f"/api/v1/setup/sessions/{sid}/answers", json={"answers": _FULL_ANSWERS})
    response = client.post(f"/api/v1/setup/sessions/{sid}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["psychogram_analysis"]
    assert data["psychogram_analysis_status"] == "ready"


def test_setup_active_session_blocks_new_setup(client):
    auth = _register(client, "setup-block-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    client.post(f"/api/v1/setup/sessions/{sid}/answers", json={"answers": _FULL_ANSWERS})
    client.post(f"/api/v1/setup/sessions/{sid}/complete")

    response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": auth["user_id"], "auth_token": auth["auth_token"], "language": "en"},
    )
    assert response.status_code in (200, 409)
    if response.status_code == 200:
        assert response.json().get("has_active_session") is True or "dashboard" in response.json()


def test_setup_answers_partial_still_returns_200(client):
    auth = _register(client, "setup-partial-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    response = client.post(
        f"/api/v1/setup/sessions/{sid}/answers",
        json={"answers": [{"question_id": "q1_rule_structure", "value": 6}]},
    )
    assert response.status_code == 200


def test_setup_complete_session_has_policy_and_psychogram(client):
    auth = _register(client, "setup-snap-user")
    setup = _start_setup(client, auth)
    sid = setup["setup_session_id"]

    client.post(f"/api/v1/setup/sessions/{sid}/answers", json={"answers": _FULL_ANSWERS})
    complete = client.post(f"/api/v1/setup/sessions/{sid}/complete")
    chastity_session = complete.json()["chastity_session"]

    assert "policy" in chastity_session
    assert "psychogram" in chastity_session
    assert isinstance(chastity_session["policy"], dict)
    assert isinstance(chastity_session["psychogram"], dict)
