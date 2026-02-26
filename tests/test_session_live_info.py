import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from chastease import create_app
from chastease.models import ChastitySession, Turn


def _register_user(client, username="reg-user", password="demo-pass-123") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _create_active_session(client, auth: dict, language: str = "en") -> str:
    payload = {"user_id": auth["user_id"], "auth_token": auth["auth_token"], "language": language}
    start = client.post("/api/v1/setup/sessions", json=payload)
    assert start.status_code == 200
    sid = start.json()["setup_session_id"]
    answers = client.post(
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
    assert answers.status_code == 200
    answers_data = answers.json()

    session_id = str(uuid4())
    db = client.app.state.db_session_factory()
    try:
        db.add(
            ChastitySession(
                id=session_id,
                user_id=auth["user_id"],
                character_id=None,
                status="active",
                language=language,
                policy_snapshot_json=json.dumps(answers_data["policy_preview"]),
                psychogram_snapshot_json=json.dumps(answers_data["psychogram_preview"]),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()
    return session_id


def _insert_turn(client: TestClient, session_id: str, turn_no: int, player_action: str, ai_narration: str):
    db = client.app.state.db_session_factory()
    try:
        db.add(
            Turn(
                id=str(uuid4()),
                session_id=session_id,
                turn_no=turn_no,
                player_action=player_action,
                ai_narration=ai_narration,
                language="de",
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()


def test_live_session_endpoint_allows_wearer_token(client):
    auth = _register_user(client, "wearer-live")
    session_id = _create_active_session(client, auth)
    _insert_turn(client, session_id, 1, "Aktion 1", "Antwort 1")
    _insert_turn(client, session_id, 2, "Aktion 2", "Antwort 2")

    response = client.get(
        f"/api/v1/sessions/{session_id}/live",
        params={"auth_token": auth["auth_token"], "detail_level": "full", "recent_turns_limit": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_mode"] == "wearer"
    assert body["session"]["session_id"] == session_id
    assert body["session_status"]["status"] == "active"
    assert "time_context" in body
    assert "is_paused" in body["time_context"]
    assert "contract_start_date" in body["time_context"]
    assert "contract_min_end_date" in body["time_context"]
    assert "contract_max_end_date" in body["time_context"]
    assert "contract_proposed_end_date" in body["time_context"]
    assert "contract_min_duration_days" in body["time_context"]
    assert "contract_max_duration_days" in body["time_context"]
    assert "setup_context" in body
    assert body["setup_context"]["latest_setup_session_id"]
    assert isinstance(body["setup_context"]["latest_setup_session"], dict)
    linked = body["setup_context"].get("linked_setup_session") or {}
    generated_contract = ((linked.get("policy_preview") or {}).get("generated_contract") or {})
    if isinstance(generated_contract, dict) and generated_contract:
        assert generated_contract.get("text") is None
    assert body["turns"]["total"] >= 2
    assert body["turns"]["returned"] == 1
    assert body["turns"]["items"][0]["turn_no"] == 2


def test_live_session_endpoint_allows_ai_token(monkeypatch, tmp_path):
    monkeypatch.setenv("SETUP_STORE_PATH", str(tmp_path / "setup_sessions.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'chastease_test.db'}")
    monkeypatch.setenv("AI_SESSION_READ_TOKEN", "ai-live-token")

    app = create_app()
    with TestClient(app) as ai_client:
        auth = _register_user(ai_client, "wearer-ai-live")
        session_id = _create_active_session(ai_client, auth)

        response = ai_client.get(
            f"/api/v1/sessions/{session_id}/live",
            params={"ai_access_token": "ai-live-token", "detail_level": "full"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["access_mode"] == "ai"
        assert body["session"]["session_id"] == session_id


def test_live_session_endpoint_rejects_missing_tokens(client):
    auth = _register_user(client, "wearer-live-no-token")
    session_id = _create_active_session(client, auth)

    response = client.get(f"/api/v1/sessions/{session_id}/live")
    assert response.status_code == 401


def test_live_session_endpoint_light_mode_excludes_setup_and_turns(client):
    """Light mode should only return session_status and time_context."""
    auth = _register_user(client, "wearer-light-mode")
    session_id = _create_active_session(client, auth)
    _insert_turn(client, session_id, 1, "Light test", "Light response")

    response = client.get(
        f"/api/v1/sessions/{session_id}/live",
        params={"auth_token": auth["auth_token"], "detail_level": "light"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["detail_level"] == "light"
    assert body["access_mode"] == "wearer"
    
    # Light mode includes these
    assert "session_status" in body
    assert "time_context" in body
    assert body["session_status"]["status"] == "active"
    assert "is_paused" in body["time_context"]
    assert "runtime_timer" in body["time_context"]
    
    # Light mode excludes these
    assert "session" not in body  # No full session object
    assert "setup_context" not in body  # No setup details
    assert "turns" not in body  # No turn history


def test_live_session_endpoint_full_mode_includes_all_data(client):
    """Full mode should include session, setup_context, and turns."""
    auth = _register_user(client, "wearer-full-mode")
    session_id = _create_active_session(client, auth)
    _insert_turn(client, session_id, 1, "Full test", "Full response")

    response = client.get(
        f"/api/v1/sessions/{session_id}/live",
        params={"auth_token": auth["auth_token"], "detail_level": "full", "recent_turns_limit": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["detail_level"] == "full"
    assert body["access_mode"] == "wearer"
    
    # Full mode includes everything
    assert "session_status" in body
    assert "time_context" in body
    assert "session" in body  # Full session object
    assert "setup_context" in body  # Setup details
    assert "turns" in body  # Turn history
    
    assert body["session"]["session_id"] == session_id
    assert body["turns"]["total"] >= 1
    assert body["turns"]["returned"] == 1
    assert body["setup_context"]["latest_setup_session_id"]


def test_live_session_endpoint_defaults_to_light_mode(client):
    """When detail_level is omitted, should default to 'light'."""
    auth = _register_user(client, "wearer-default-mode")
    session_id = _create_active_session(client, auth)

    response = client.get(
        f"/api/v1/sessions/{session_id}/live",
        params={"auth_token": auth["auth_token"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["detail_level"] == "light"
    assert "session" not in body  # Light mode excludes full session
    assert "setup_context" not in body
    assert "turns" not in body
