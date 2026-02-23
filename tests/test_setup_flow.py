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
    assert data["questions"][0]["scale_max"] == 100
    assert data["questions"][0]["scale_left"] == "does not apply"
    assert data["questions"][0]["scale_right"] == "applies strongly"


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


def test_setup_start_persists_ttlock_integration_config(client):
    auth = _register(client, "ttlock-config-user", "TTLock Config User")
    user_id = auth["user_id"]
    payload = {
        "user_id": user_id,
        "auth_token": auth["auth_token"],
        "integrations": ["ttlock"],
        "integration_config": {
            "ttlock": {
                "ttl_user": "wearer@example.com",
                "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                "ttl_gateway_id": "gw-1",
                "ttl_lock_id": "lock-1",
            }
        },
    }
    start_response = client.post("/api/v1/setup/sessions", json=payload)
    assert start_response.status_code == 200
    start_data = start_response.json()
    assert start_data["integrations"] == ["ttlock"]
    assert start_data["integration_config"]["ttlock"]["ttl_user"] == "wearer@example.com"
    assert start_data["integration_config"]["ttlock"]["ttl_lock_id"] == "lock-1"

    setup_session_id = start_data["setup_session_id"]
    get_response = client.get(f"/api/v1/setup/sessions/{setup_session_id}")
    assert get_response.status_code == 200
    session = get_response.json()
    assert session["integrations"] == ["ttlock"]
    assert session["integration_config"]["ttlock"]["ttl_gateway_id"] == "gw-1"


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


def test_setup_start_allows_ai_defined_end_without_max_date(client):
    auth = _register(client, "ai-end-user", "AI End User")
    response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "contract_start_date": "2026-03-01",
            "contract_max_end_date": None,
            "ai_controls_end_date": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract"]["start_date"] == "2026-03-01"
    assert data["contract"]["max_end_date"] is None
    assert data["contract"]["ai_controls_end_date"] is True


def test_kill_active_session_enables_new_setup(client):
    auth = _register(client, "kill-user", "Kill User")
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
                {"question_id": "q4_praise_importance", "value": 4},
                {"question_id": "q5_novelty_challenge", "value": 8},
                {"question_id": "q6_intensity_1_5", "value": 4},
            ]
        },
    )
    client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")

    kill_response = client.delete(
        f"/api/v1/sessions/active?user_id={user_id}&auth_token={auth['auth_token']}"
    )
    assert kill_response.status_code == 200
    assert kill_response.json()["deleted"] is True

    active_response = client.get(
        f"/api/v1/sessions/active?user_id={user_id}&auth_token={auth['auth_token']}"
    )
    assert active_response.status_code == 200
    assert active_response.json()["has_active_session"] is False

    new_start = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert new_start.status_code == 200


def test_contract_consent_updates_signature_and_footer(client, monkeypatch):
    from chastease.api.routers import setup as setup_router

    monkeypatch.setattr(
        setup_router,
        "generate_psychogram_analysis_with_end_date_for_setup",
        lambda *_args, **_kwargs: ("Analyse bereit.", "2026-03-15"),
    )
    monkeypatch.setattr(
        setup_router,
        "generate_contract_for_setup",
        lambda *_args, **_kwargs: (
            "# Keuschheits-Vertrag\n\n"
            "## Signatur\n"
            "- Datum: ***2026-03-01***\n"
            "- Unterschrift Sub: ***[signatur ausstehend]***\n\n"
            "Technischer Footer:\n"
            "```json\n"
            "{\n"
            '  "consent_accepted": "false",\n'
            '  "consent_text": "-",\n'
            '  "consent_accepted_at": "-"\n'
            "}\n"
            "```"
        ),
    )

    auth = _register(client, "consent-user", "Consent User")
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
                {"question_id": "q4_praise_importance", "value": 4},
                {"question_id": "q5_novelty_challenge", "value": 8},
                {"question_id": "q6_intensity_1_5", "value": 4},
            ]
        },
    )
    complete_response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200

    artifacts_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/artifacts",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert artifacts_response.status_code == 200

    accept_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/contract/accept",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "consent_text": "Ich akzeptiere diesen Vertrag",
        },
    )
    assert accept_response.status_code == 200
    data = accept_response.json()
    contract_text = str(data["contract_text"])
    assert data["consent"]["accepted"] is True
    assert data["consent"]["accepted_at"]
    assert '"consent_accepted": "true"' in contract_text
    assert '"consent_accepted_at": "-"' not in contract_text
    assert "[signatur ausstehend]" not in contract_text
