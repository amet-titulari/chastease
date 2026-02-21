def _register(client, username, name="Wearer", password="demo-pass-123", email=None):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "display_name": name,
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_setup_session_lifecycle(client):
    auth = _register(client, "wearer-123", "Wearer 123")
    user_id = auth["user_id"]

    start_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "hard_stop_enabled": True,
            "autonomy_mode": "execute",
            "integrations": ["ttlock", "chaster"],
        },
    )
    assert start_response.status_code == 200
    start_data = start_response.json()
    setup_session_id = start_data["setup_session_id"]
    assert start_data["status"] == "setup_in_progress"
    assert len(start_data["questions"]) > 0

    answers_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 4},
                {"question_id": "q5_novelty_challenge", "value": 8},
                {"question_id": "q6_intensity_1_5", "value": 4},
                {"question_id": "q8_instruction_style", "value": "mixed"},
                {"question_id": "q9_open_context", "value": "Heute nur kurze Session."},
            ]
        },
    )
    assert answers_response.status_code == 200
    answers_data = answers_response.json()
    assert answers_data["answered_questions"] == 8
    assert "psychogram_preview" in answers_data
    assert "policy_preview" in answers_data
    assert "psychogram_brief" in answers_data
    assert "autonomy_profile" in answers_data["psychogram_preview"]["interaction_preferences"]
    assert "praise_timing" in answers_data["psychogram_preview"]["interaction_preferences"]

    get_response = client.get(f"/api/v1/setup/sessions/{setup_session_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["user_id"] == user_id
    assert get_data["status"] == "setup_in_progress"

    complete_response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200
    complete_data = complete_response.json()
    assert complete_data["status"] == "configured"
    assert complete_data["chastity_session"]["status"] == "active"
    assert complete_data["chastity_session"]["user_id"] == user_id


def test_setup_session_returns_english_questions(client):
    auth = _register(client, "wearer-en", "Wearer EN")
    user_id = auth["user_id"]
    response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"], "language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"
    assert data["questions"][0]["text"].startswith("How important")
    assert data["questions"][0]["scale_min"] == 1
    assert data["questions"][0]["scale_max"] == 10


def test_setup_start_requires_valid_token(client):
    response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": "does-not-exist", "auth_token": "invalid-token"},
    )
    assert response.status_code == 401


def test_setup_complete_requires_min_answers(client):
    auth = _register(client, "wearer-xyz", "Wearer XYZ")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"], "autonomy_mode": "suggest"},
    )
    setup_session_id = start_response.json()["setup_session_id"]

    response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert response.status_code == 400


def test_setup_persists_to_store(client):
    auth = _register(client, "persist-user", "Persist Test")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"], "language": "en"},
    )
    setup_session_id = start_response.json()["setup_session_id"]

    get_response = client.get(f"/api/v1/setup/sessions/{setup_session_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["user_id"] == user_id
    assert data["language"] == "en"


def test_low_confidence_applies_conservative_defaults(client):
    auth = _register(client, "low-conf-user", "Low Conf")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    setup_session_id = start_response.json()["setup_session_id"]

    answers_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
        json={"answers": [{"question_id": "q1_rule_structure", "value": 6}]},
    )
    assert answers_response.status_code == 200
    policy = answers_response.json()["policy_preview"]
    assert policy["conservative_defaults"]["applied"] is True
    assert policy["interaction_profile"]["autonomy_profile"] == "suggest_first"
    assert policy["limits"]["max_intensity_level"] == 2


def test_psychogram_recalibration_updates_metadata(client):
    auth = _register(client, "recal-user", "Recal")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    setup_session_id = start_response.json()["setup_session_id"]

    client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 5},
                {"question_id": "q5_novelty_challenge", "value": 7},
                {"question_id": "q6_intensity_1_5", "value": 4},
                {"question_id": "q8_instruction_style", "value": "direct_command"},
            ]
        },
    )

    patch_response = client.patch(
        f"/api/v1/setup/sessions/{setup_session_id}/psychogram",
        json={"update_reason": "mid_session_calibration", "trait_overrides": {"strictness_affinity": 85}},
    )
    assert patch_response.status_code == 200
    data = patch_response.json()
    assert data["psychogram"]["update_reason"] == "mid_session_calibration"
    assert data["psychogram"]["updated_at"] is not None
    assert data["psychogram"]["traits"]["strictness_affinity"] == 85


def test_active_session_blocks_new_setup_and_returns_dashboard_payload(client):
    auth = _register(client, "active-session-user", "Active Session")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

    client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 4},
                {"question_id": "q5_novelty_challenge", "value": 8},
                {"question_id": "q6_intensity_1_5", "value": 4},
            ]
        },
    )
    complete_response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200

    active_response = client.get(
        f"/api/v1/sessions/active?user_id={user_id}&auth_token={auth['auth_token']}"
    )
    assert active_response.status_code == 200
    active_data = active_response.json()
    assert active_data["has_active_session"] is True
    assert active_data["chastity_session"]["user_id"] == user_id
    assert active_data["chastity_session"]["status"] == "active"

    second_start = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert second_start.status_code == 409


def test_setup_start_contract_dates_and_limits_are_persisted(client):
    auth = _register(client, "contract-user", "Contract User")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "contract_start_date": "2026-03-01",
            "contract_max_end_date": "2026-03-10",
            "max_penalty_per_day_minutes": 45,
            "max_penalty_per_week_minutes": 180,
            "opening_limit_period": "week",
            "max_openings_in_period": 2,
            "opening_window_minutes": 25,
        },
    )
    assert start_response.status_code == 200
    data = start_response.json()
    assert data["contract"]["start_date"] == "2026-03-01"
    assert data["contract"]["end_date"] is None
    assert data["contract"]["max_end_date"] == "2026-03-10"
    assert data["contract"]["ai_controls_end_date"] is True
    assert data["contract"]["max_penalty_per_day_minutes"] == 45
    assert data["contract"]["max_penalty_per_week_minutes"] == 180
    assert data["contract"]["opening_limit_period"] == "week"
    assert data["contract"]["max_openings_in_period"] == 2
    assert data["contract"]["opening_window_minutes"] == 25


def test_setup_start_rejects_end_before_start(client):
    auth = _register(client, "contract-invalid-user", "Contract Invalid User")
    user_id = auth["user_id"]
    response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "contract_start_date": "2026-03-10",
            "contract_end_date": "2026-03-01",
        },
    )
    assert response.status_code == 400


def test_setup_start_accepts_disabled_penalty_caps(client):
    auth = _register(client, "no-penalty-user", "No Penalty")
    response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "max_penalty_per_day_minutes": 0,
            "max_penalty_per_week_minutes": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract"]["max_penalty_per_day_minutes"] == 0
    assert data["contract"]["max_penalty_per_week_minutes"] == 0
