def test_story_turn_requires_action(client):
    response = client.post("/api/v1/story/turn", json={"session_id": "missing"})
    assert response.status_code == 422


def test_story_turn_requires_session_id(client):
    response = client.post("/api/v1/story/turn", json={"action": "Ich oeffne die Truhe."})
    assert response.status_code == 400


def test_story_turn_persistent_flow(client):
    setup_response = client.post(
        "/api/v1/setup/sessions",
        json={"wearer_id": "wearer-story", "language": "en"},
    )
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
    session_id = complete_response.json()["chastity_session"]["session_id"]

    response1 = client.post(
        "/api/v1/story/turn",
        json={"session_id": session_id, "action": "I follow the instruction.", "language": "en"},
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["turn_no"] == 1

    response2 = client.post(
        "/api/v1/story/turn",
        json={"session_id": session_id, "action": "I report back.", "language": "en"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["turn_no"] == 2

    turns_response = client.get(f"/api/v1/sessions/{session_id}/turns")
    assert turns_response.status_code == 200
    turns_data = turns_response.json()
    assert len(turns_data["turns"]) == 2
