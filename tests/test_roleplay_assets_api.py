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
    assert "roleplay_debug" in active_body["chastity_session"]
    assert "Prompt profile:" in active_body["chastity_session"]["roleplay_debug"]["prompt_preview"]
    assert isinstance(active_body["chastity_session"]["roleplay_debug"]["selected_memory_entries"], list)
    assert isinstance(active_body["chastity_session"]["roleplay_debug"]["selected_scene_beats"], list)
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


def test_roleplay_asset_export_import_roundtrip(client):
    source_user_id, source_auth_token = _register_user(client, "rp-export-source")

    created_character = client.post(
        "/api/v1/roleplay/characters",
        json={
            "user_id": source_user_id,
            "auth_token": source_auth_token,
            "display_name": "Ledger Keeper",
            "persona_name": "Ledger",
            "description": "Tracks continuity and compliance.",
            "greeting_template": "Open the ledger and report.",
            "tone": "clinical",
            "dominance_style": "controlled",
            "ritual_phrases": ["State your status."],
            "goals": ["track continuity"],
            "scenario_hooks": ["ledger"],
            "tags": ["library"],
        },
    )
    assert created_character.status_code == 200

    created_scenario = client.post(
        "/api/v1/roleplay/scenarios",
        json={
            "user_id": source_user_id,
            "auth_token": source_auth_token,
            "title": "Ledger Review",
            "summary": "Review every report against the running record.",
            "phase_title": "Review",
            "phase_objective": "Keep reports concise.",
            "phase_guidance": "Compare the current answer to earlier statements.",
            "lore_content": "The ledger is the source of continuity.",
            "lore_triggers": ["ledger", "review"],
            "tags": ["library"],
        },
    )
    assert created_scenario.status_code == 200

    exported = client.get(
        f"/api/v1/roleplay/export?user_id={source_user_id}&auth_token={source_auth_token}&language=en"
    )
    assert exported.status_code == 200
    export_body = exported.json()
    assert export_body["schema_version"] == 1
    assert any(item["display_name"] == "Ledger Keeper" for item in export_body["characters"])
    assert any(item["title"] == "Ledger Review" for item in export_body["scenarios"])
    assert all(not item.get("builtin") for item in export_body["characters"])

    target_user_id, target_auth_token = _register_user(client, "rp-export-target")
    imported = client.post(
        "/api/v1/roleplay/import",
        json={
            "user_id": target_user_id,
            "auth_token": target_auth_token,
            "library": export_body,
        },
    )
    assert imported.status_code == 200
    import_body = imported.json()
    assert import_body["imported"] == {"characters": 1, "scenarios": 1}
    assert import_body["characters"][0]["display_name"] == "Ledger Keeper"
    assert import_body["scenarios"][0]["title"] == "Ledger Review"

    target_library = client.get(
        f"/api/v1/roleplay/library?user_id={target_user_id}&auth_token={target_auth_token}&language=en"
    )
    assert target_library.status_code == 200
    target_library_body = target_library.json()
    assert any(item["display_name"] == "Ledger Keeper" for item in target_library_body["characters"])
    assert any(item["title"] == "Ledger Review" for item in target_library_body["scenarios"])


def test_roleplay_asset_import_duplicates_when_not_overwriting(client):
    user_id, auth_token = _register_user(client, "rp-import-duplicate")

    created_character = client.post(
        "/api/v1/roleplay/characters",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "display_name": "Archive Voice",
            "persona_name": "Archive Voice",
            "description": "Original asset.",
            "greeting_template": "Original greeting.",
            "tone": "precise",
            "dominance_style": "measured",
            "ritual_phrases": [],
            "goals": [],
            "scenario_hooks": [],
            "tags": ["original"],
        },
    )
    assert created_character.status_code == 200
    character_id = created_character.json()["character"]["asset_id"]

    imported = client.post(
        "/api/v1/roleplay/import",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "library": {
                "characters": [
                    {
                        "asset_id": character_id,
                        "display_name": "Archive Voice",
                        "persona": {
                            "name": "Archive Voice",
                            "archetype": "keyholder",
                            "description": "Imported copy.",
                            "goals": ["track"],
                            "speech_style": {
                                "tone": "calm",
                                "dominance_style": "firm",
                                "ritual_phrases": ["Report."],
                                "formatting_style": "plain",
                            },
                        },
                        "greeting_template": "Imported greeting.",
                        "scenario_hooks": ["archive"],
                        "tags": ["imported"],
                    }
                ],
                "scenarios": [],
            },
        },
    )
    assert imported.status_code == 200
    import_body = imported.json()
    assert import_body["imported"] == {"characters": 1, "scenarios": 0}
    assert import_body["characters"][0]["asset_id"] != character_id

    library = client.get(
        f"/api/v1/roleplay/library?user_id={user_id}&auth_token={auth_token}&language=en"
    )
    assert library.status_code == 200
    custom_characters = [item for item in library.json()["characters"] if not item.get("builtin")]
    assert len(custom_characters) == 2


def test_roleplay_asset_import_overwrites_when_enabled(client):
    user_id, auth_token = _register_user(client, "rp-import-overwrite")

    created_character = client.post(
        "/api/v1/roleplay/characters",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "display_name": "Archive Voice",
            "persona_name": "Archive Voice",
            "description": "Original asset.",
            "greeting_template": "Original greeting.",
            "tone": "precise",
            "dominance_style": "measured",
            "ritual_phrases": [],
            "goals": [],
            "scenario_hooks": [],
            "tags": ["original"],
        },
    )
    assert created_character.status_code == 200
    character_id = created_character.json()["character"]["asset_id"]

    imported = client.post(
        "/api/v1/roleplay/import",
        json={
            "user_id": user_id,
            "auth_token": auth_token,
            "overwrite_existing": True,
            "library": {
                "characters": [
                    {
                        "asset_id": character_id,
                        "display_name": "Archive Voice",
                        "persona": {
                            "name": "Archive Voice",
                            "archetype": "keyholder",
                            "description": "Imported overwrite.",
                            "goals": ["track"],
                            "speech_style": {
                                "tone": "calm",
                                "dominance_style": "firm",
                                "ritual_phrases": ["Report."],
                                "formatting_style": "plain",
                            },
                        },
                        "greeting_template": "Imported greeting.",
                        "scenario_hooks": ["archive"],
                        "tags": ["imported"],
                    }
                ],
                "scenarios": [],
            },
        },
    )
    assert imported.status_code == 200
    import_body = imported.json()
    assert import_body["imported"] == {"characters": 1, "scenarios": 0}
    assert import_body["characters"][0]["asset_id"] == character_id

    library = client.get(
        f"/api/v1/roleplay/library?user_id={user_id}&auth_token={auth_token}&language=en"
    )
    assert library.status_code == 200
    custom_characters = [item for item in library.json()["characters"] if not item.get("builtin")]
    assert len(custom_characters) == 1
    assert custom_characters[0]["asset_id"] == character_id
    assert custom_characters[0]["greeting_template"] == "Imported greeting."
    assert custom_characters[0]["persona"]["description"] == "Imported overwrite."