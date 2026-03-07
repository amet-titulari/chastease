def _register_user(client, username: str) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "display_name": username,
            "password": "demo-pass-123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    return body["user_id"], body["auth_token"]


def test_roleplay_assets_flow_from_library_to_active_session(client):
    user_id, auth_token = _register_user(client, "rp-assets-user")

    library_response = client.get(
        f"/api/v1/roleplay/library?user_id={user_id}&auth_token={auth_token}&language=en"
    )
    assert library_response.status_code == 200
    library_body = library_response.json()
    assert any(item["asset_id"] == "builtin-keyholder" for item in library_body["characters"])
    assert any(item["asset_id"] == "guided-chastity-session" for item in library_body["scenarios"])

    character_response = client.post(
        "/api/v1/roleplay/characters",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "display_name": "Archivist Keyholder",
            "persona_name": "Archivist",
            "description": "Precise, observant and continuity-focused.",
            "greeting_template": "Archivist: Report every deviation.",
            "tone": "precise",
            "dominance_style": "measured",
            "ritual_phrases": ["State your condition."],
            "goals": ["preserve continuity", "maintain control"],
            "scenario_hooks": ["archive", "ritual"],
            "tags": ["custom", "strict"],
        },
    )
    assert character_response.status_code == 200
    character_id = character_response.json()["character"]["asset_id"]

    scenario_response = client.post(
        "/api/v1/roleplay/scenarios",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "title": "Inspection Cycle",
            "summary": "A recurring inspection-driven session frame.",
            "phase_title": "Inspection",
            "phase_objective": "Keep the wearer reporting accurately.",
            "phase_guidance": "Ask for concise status reports and small ritual confirmations.",
            "lore_content": "Every report is logged and reviewed against prior conduct.",
            "lore_triggers": ["report", "inspection"],
            "tags": ["custom", "inspection"],
        },
    )
    assert scenario_response.status_code == 200
    scenario_id = scenario_response.json()["scenario"]["asset_id"]

    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "language": "en",
            "roleplay_character_id": character_id,
            "roleplay_scenario_id": scenario_id,
        },
    )
    assert setup_response.status_code == 200
    setup_session_id = setup_response.json()["setup_session_id"]

    answers_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/answers",
        json={
            "answers": [
                {"question_id": "q1_rule_structure", "value": 8},
                {"question_id": "q2_strictness_authority", "value": 7},
                {"question_id": "q3_control_need", "value": 8},
                {"question_id": "q4_praise_importance", "value": 4},
                {"question_id": "q5_novelty_challenge", "value": 7},
                {"question_id": "q6_intensity_1_5", "value": 4},
                {"question_id": "q8_instruction_style", "value": "mixed"},
                {"question_id": "q9_open_context", "value": "Prepared for inspection."},
            ]
        },
    )
    assert answers_response.status_code == 200

    setup_state = client.get(f"/api/v1/setup/sessions/{setup_session_id}")
    assert setup_state.status_code == 200
    setup_body = setup_state.json()
    assert setup_body["roleplay_character_id"] == character_id
    assert setup_body["roleplay_scenario_id"] == scenario_id
    assert setup_body["roleplay_profile"]["character_card"]["display_name"] == "Archivist Keyholder"
    assert setup_body["roleplay_profile"]["scenario"]["title"] == "Inspection Cycle"

    complete_response = client.post(f"/api/v1/setup/sessions/{setup_session_id}/complete")
    assert complete_response.status_code == 200

    active_response = client.get(
        f"/api/v1/sessions/active?user_id={user_id}&auth_token={auth_token}"
    )
    assert active_response.status_code == 200
    active_body = active_response.json()
    assert active_body["has_active_session"] is True
    assert active_body["chastity_session"]["roleplay_character_id"] == character_id
    assert active_body["chastity_session"]["roleplay_scenario_id"] == scenario_id
    assert active_body["chastity_session"]["policy"]["roleplay"]["selection"] == {
        "character_id": character_id,
        "scenario_id": scenario_id,
    }

    selection_response = client.post(
        f"/api/v1/setup/sessions/{setup_session_id}/roleplay",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "roleplay_character_id": "builtin-keyholder",
            "roleplay_scenario_id": "guided-chastity-session",
        },
    )
    assert selection_response.status_code == 200
    assert selection_response.json()["applied_to_active_session"] is True

    active_after_switch = client.get(
        f"/api/v1/sessions/active?user_id={user_id}&auth_token={auth_token}"
    )
    assert active_after_switch.status_code == 200
    switched_body = active_after_switch.json()
    assert switched_body["chastity_session"]["roleplay_character_id"] == "builtin-keyholder"
    assert switched_body["chastity_session"]["roleplay_scenario_id"] == "guided-chastity-session"