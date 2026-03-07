import json
from datetime import UTC, datetime
from uuid import uuid4

from chastease.models import ChastitySession


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
    assert answers_data["answered_questions"] >= 8
    assert "psychogram_preview" in answers_data
    assert "policy_preview" in answers_data
    assert "psychogram_brief" in answers_data
    assert "psychogram_analysis" not in answers_data
    session_after_answers = client.get(f"/api/v1/setup/sessions/{setup_session_id}").json()
    assert session_after_answers["psychogram_analysis"] is None
    assert session_after_answers["psychogram_analysis_status"] == "idle"
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
    assert complete_data["psychogram_analysis_status"] == "ready"
    assert complete_data["psychogram_analysis"]
    assert complete_data["chastity_session"]["status"] == "active"
    assert complete_data["chastity_session"]["user_id"] == user_id
    assert complete_data["chastity_session"]["psychogram_analysis"]
    roleplay_profile = complete_data["chastity_session"]["policy"]["roleplay"]
    assert roleplay_profile["character_card"]["display_name"] == "Amet Titulari"
    assert roleplay_profile["scenario"]["title"] == "Amet Titulari Devotion Protocol"


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


def test_roleplay_selection_refreshes_policy_preview_when_missing(client):
    auth = _register(client, "roleplay-refresh-user", "Roleplay Refresh")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"], "language": "de"},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

    selection_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/roleplay",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "roleplay_character_id": "builtin-keyholder",
            "roleplay_scenario_id": "guided-chastity-session",
            "prompt_profile_name": "amet-session",
            "prompt_profile_mode": "immersive",
            "prompt_profile_version": "v1",
        },
    )
    assert selection_response.status_code == 200
    data = selection_response.json()
    assert data["roleplay_character_id"] == "builtin-keyholder"
    assert data["roleplay_scenario_id"] == "guided-chastity-session"
    assert data["roleplay_profile"]["prompt_profile"] == {
        "name": "amet-session",
        "version": "v1",
        "mode": "immersive",
    }

    setup_state = client.get(f"/api/v1/setup/sessions/{setup_session_id}")
    assert setup_state.status_code == 200
    setup_body = setup_state.json()
    assert isinstance(setup_body["policy_preview"], dict)
    assert setup_body["policy_preview"]["roleplay"]["prompt_profile"]["mode"] == "immersive"


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


def test_setup_start_rejects_incomplete_ttlock_integration_config(client):
    auth = _register(client, "ttlock-incomplete-user", "TTLock Incomplete User")
    user_id = auth["user_id"]
    payload = {
        "user_id": user_id,
        "auth_token": auth["auth_token"],
        "integrations": ["ttlock"],
        "integration_config": {"ttlock": {"ttl_user": "wearer@example.com"}},
    }
    response = client.post("/api/v1/setup/sessions", json=payload)
    assert response.status_code == 400
    assert "ttl_user, ttl_pass_md5 and ttl_lock_id" in response.json()["detail"]


def test_setup_start_seeds_ttlock_config_from_last_session(client):
    auth = _register(client, "ttlock-seed-user", "TTLock Seed User")
    user_id = auth["user_id"]

    db = client.app.state.db_session_factory()
    try:
        seeded_policy = {
            "integrations": ["ttlock"],
            "integration_config": {
                "ttlock": {
                    "ttl_user": "seed-user@example.com",
                    "ttl_pass_md5": "0123456789abcdef0123456789abcdef",
                    "ttl_gateway_id": "gw-seed",
                    "ttl_lock_id": "lock-seed",
                }
            },
        }
        historical_session = ChastitySession(
            id=str(uuid4()),
            user_id=user_id,
            character_id=None,
            status="finished",
            language="de",
            policy_snapshot_json=json.dumps(seeded_policy),
            psychogram_snapshot_json=json.dumps({}),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(historical_session)
        db.commit()
    finally:
        db.close()

    start_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "integrations": [],
            "integration_config": {},
        },
    )
    assert start_response.status_code == 200
    data = start_response.json()
    assert "ttlock" in data["integrations"]
    assert data["integration_config"]["ttlock"]["ttl_user"] == "seed-user@example.com"
    assert data["integration_config"]["ttlock"]["ttl_lock_id"] == "lock-seed"


def test_ai_update_fields_blocked_in_suggest_mode(client):
    auth = _register(client, "ai-suggest-user", "AI Suggest")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"], "autonomy_mode": "suggest"},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

    response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/ai-update-fields",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "updates": {"opening_window_minutes": 60, "max_intensity_level": 5},
            "reason": "adapt to wearer state",
        },
    )
    assert response.status_code == 409
    assert "autonomy_mode='suggest'" in response.json()["detail"]


def test_ai_update_fields_apply_immediately_and_are_audited(admin_client):
    auth = _register(admin_client, "ai-exec-user", "AI Exec")
    user_id = auth["user_id"]
    start_response = admin_client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"], "autonomy_mode": "execute"},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

    answers_response = admin_client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 70},
                {"question_id": "q2_strictness_authority", "value": 70},
                {"question_id": "q3_control_need", "value": 70},
                {"question_id": "q4_praise_importance", "value": 40},
                {"question_id": "q5_novelty_challenge", "value": 70},
                {"question_id": "q9_open_context", "value": "ready"},
            ]
        },
    )
    assert answers_response.status_code == 200

    complete_response = admin_client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200
    active_session_id = complete_response.json()["chastity_session"]["session_id"]

    update_response = admin_client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/ai-update-fields",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "updates": {
                "opening_window_minutes": 75,
                "max_intensity_level": 5,
                "instruction_style": "direct_command",
            },
            "reason": "wearer requested stricter direct handling",
        },
    )
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["applied_to_active_session"] is True
    assert update_data["audit_logged_count"] >= 3

    active_response = admin_client.get(
        f"/api/v1/sessions/active?user_id={user_id}&auth_token={auth['auth_token']}"
    )
    assert active_response.status_code == 200
    policy = active_response.json()["chastity_session"]["policy"]
    assert policy["limits"]["opening_window_minutes"] == 75
    assert policy["limits"]["max_intensity_level"] == 5
    assert policy["interaction_profile"]["instruction_style"] == "direct_command"

    audit_response = admin_client.get(
        f"/api/v1/admin/audit/session/{active_session_id}?auth_token={auth['auth_token']}"
    )
    assert audit_response.status_code == 200
    entries = audit_response.json()["entries"]
    ai_entries = [entry for entry in entries if entry["event_type"] == "ai_controlled_field_updated"]
    assert len(ai_entries) >= 3
    assert any(entry["metadata"].get("field") == "opening_window_minutes" for entry in ai_entries)
    assert any(entry["metadata"].get("field") == "max_intensity_level" for entry in ai_entries)


def test_ai_calibration_turn_returns_question_and_updates_inferred(client):
    auth = _register(client, "ai-calib-user", "AI Calib")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

    init_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/ai-calibration-turn",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert init_response.status_code == 200
    init_data = init_response.json()
    assert init_data["next_question"]

    turn_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/ai-calibration-turn",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "wearer_message": "Bitte direkt und stark, Eskalation langsam, Intimrasur getrimmt.",
        },
    )
    assert turn_response.status_code == 200
    turn_data = turn_response.json()
    inferred = turn_data["inferred"]
    assert inferred["instruction_style"] == "direct_command"
    assert inferred["desired_intensity"] == "strong"
    assert inferred["escalation_mode"] == "slow"
    assert inferred["grooming_preference"] == "trimmed"
    assert turn_data["turns_count"] >= 1

    session_data = client.get(f"/api/v1/setup/sessions/{setup_session_id}").json()
    assert session_data["instruction_style"] == "direct_command"
    assert session_data["desired_intensity"] == "strong"
    assert session_data["grooming_preference"] == "trimmed"
    assert session_data["escalation_mode"] == "slow"


def test_psychogram_answers_override_default_escalation_and_map_experience_40_to_intermediate(client):
    auth = _register(client, "psychogram-pref-user", "Psychogram Pref")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

    answers_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 60},
                {"question_id": "q2_strictness_authority", "value": 60},
                {"question_id": "q3_control_need", "value": 65},
                {"question_id": "q4_praise_importance", "value": 50},
                {"question_id": "q5_novelty_challenge", "value": 80},
                {"question_id": "q11_escalation_mode", "value": "strong"},
                {"question_id": "q13_experience_level", "value": 40},
            ]
        },
    )
    assert answers_response.status_code == 200
    interaction = answers_response.json()["psychogram_preview"]["interaction_preferences"]
    assert interaction["escalation_mode"] == "strong"
    assert interaction["experience_level"] == 4
    assert interaction["experience_profile"] == "intermediate"


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


def test_setup_integrations_update_syncs_to_active_session(client):
    auth = _register(client, "ttlock-sync-user", "TTLock Sync User")
    user_id = auth["user_id"]

    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

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
            ]
        },
    )
    assert answers_response.status_code == 200

    complete_response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200
    session_id = complete_response.json()["chastity_session"]["session_id"]

    update_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/integrations",
        json={
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
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["applied_to_active_session"] is True
    assert updated["integrations"] == ["ttlock"]

    active_response = client.get(f"/api/v1/sessions/{session_id}")
    assert active_response.status_code == 200
    policy = active_response.json()["policy"]
    assert policy["integrations"] == ["ttlock"]
    assert policy["integration_config"]["ttlock"]["ttl_lock_id"] == "lock-1"


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


def test_complete_contract_accept_reflected_in_active_session(client, monkeypatch):
    from chastease.api.routers import setup as setup_router

    monkeypatch.setattr(
        setup_router,
        "generate_psychogram_analysis_with_end_date_for_setup",
        lambda *_args, **_kwargs: ("Analyse bereit.", "2026-04-15"),
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

    auth = _register(client, "consent-active-user", "Consent Active User")
    user_id = auth["user_id"]
    start_response = client.post(
        "/api/v1/setup/sessions",
        json={"user_id": user_id, "auth_token": auth["auth_token"]},
    )
    assert start_response.status_code == 200
    setup_session_id = start_response.json()["setup_session_id"]

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
            ]
        },
    )
    assert answers_response.status_code == 200

    complete_response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200

    contract_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/contract",
        json={"user_id": user_id, "auth_token": auth["auth_token"], "force": False},
    )
    assert contract_response.status_code == 200
    assert contract_response.json()["consent"]["accepted"] is False

    accept_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/contract/accept",
        json={
            "user_id": user_id,
            "auth_token": auth["auth_token"],
            "consent_text": "Ich akzeptiere diesen Vertrag",
        },
    )
    assert accept_response.status_code == 200
    accepted = accept_response.json()
    assert accepted["consent"]["accepted"] is True
    assert accepted["consent"]["accepted_at"]

    active_response = client.get(
        f"/api/v1/sessions/active?user_id={user_id}&auth_token={auth['auth_token']}"
    )
    assert active_response.status_code == 200
    active_data = active_response.json()
    generated = ((active_data.get("chastity_session") or {}).get("policy") or {}).get("generated_contract") or {}
    assert generated.get("text")
    assert (generated.get("consent") or {}).get("accepted") is True
    assert (generated.get("consent") or {}).get("accepted_at")
