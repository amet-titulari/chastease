def test_setup_session_lifecycle(client):
    user_response = client.post("/api/v1/users", json={"email": "wearer-123@example.com", "display_name": "Wearer 123"})
    user_id = user_response.json()["user_id"]

    start_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": user_id,
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
    user_response = client.post("/api/v1/users", json={"email": "wearer-en@example.com", "display_name": "Wearer EN"})
    user_id = user_response.json()["user_id"]
    response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"
    assert data["questions"][0]["text"].startswith("How important")
    assert data["questions"][0]["scale_min"] == 1
    assert data["questions"][0]["scale_max"] == 10


def test_setup_start_requires_existing_user(client):
    response = client.post("/api/v1/setup/sessions", json={"user_id": "does-not-exist"})
    assert response.status_code == 404


def test_setup_complete_requires_min_answers(client):
    user_response = client.post("/api/v1/users", json={"email": "wearer-xyz@example.com", "display_name": "Wearer XYZ"})
    user_id = user_response.json()["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "autonomy_mode": "suggest"},
    )
    setup_session_id = start_response.json()["setup_session_id"]

    response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert response.status_code == 400


def test_setup_persists_to_store(client):
    user_response = client.post("/api/v1/users", json={"email": "persist@example.com", "display_name": "Persist Test"})
    user_id = user_response.json()["user_id"]
    start_response = client.post("/api/v1/setup/sessions", json={"user_id": user_id, "language": "en"})
    setup_session_id = start_response.json()["setup_session_id"]

    get_response = client.get(f"/api/v1/setup/sessions/{setup_session_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["user_id"] == user_id
    assert data["language"] == "en"


def test_low_confidence_applies_conservative_defaults(client):
    user_response = client.post("/api/v1/users", json={"email": "low-conf@example.com", "display_name": "Low Conf"})
    user_id = user_response.json()["user_id"]
    start_response = client.post("/api/v1/setup/sessions", json={"user_id": user_id})
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
    user_response = client.post("/api/v1/users", json={"email": "recal@example.com", "display_name": "Recal"})
    user_id = user_response.json()["user_id"]
    start_response = client.post("/api/v1/setup/sessions", json={"user_id": user_id})
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
