from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal
from app.main import app
from app.models.llm_profile import LlmProfile
from app.models.session import Session


def _register(client: TestClient, prefix: str) -> str:
    email = f"{prefix}-{uuid4().hex[:8]}@example.com"
    username = f"{prefix}-{uuid4().hex[:8]}"
    resp = client.post(
        "/auth/register",
        data={
            "username": username,
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return email


def test_owned_session_requires_owner_access():
    with TestClient(app) as owner_client:
        _register(owner_client, "session-owner")
        create_resp = owner_client.post(
            "/api/sessions",
            json={
                "persona_name": "Owned Persona",
                "player_nickname": "Owner",
                "min_duration_seconds": 300,
            },
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        owner_view = owner_client.get(f"/api/sessions/{session_id}")
        assert owner_view.status_code == 200

        owner_client.post("/auth/logout")
        anon_view = owner_client.get(f"/api/sessions/{session_id}")
        assert anon_view.status_code == 401

    with TestClient(app) as other_client:
        _register(other_client, "session-other")
        other_view = other_client.get(f"/api/sessions/{session_id}")
        assert other_view.status_code == 404


def test_legacy_unowned_session_remains_accessible_anonymously():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Legacy Persona",
                "player_nickname": "Legacy Player",
                "min_duration_seconds": 300,
            },
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        view_resp = client.get(f"/api/sessions/{session_id}")
        assert view_resp.status_code == 200


def test_completed_blueprints_are_scoped_to_owner():
    with TestClient(app) as owner_client:
        _register(owner_client, "blueprint-owner")
        create_resp = owner_client.post(
            "/api/sessions",
            json={
                "persona_name": "Blueprint Persona",
                "player_nickname": "Owner",
                "min_duration_seconds": 300,
            },
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        db = SessionLocal()
        try:
            session_obj = db.query(Session).filter(Session.id == session_id).first()
            assert session_obj is not None
            session_obj.status = "completed"
            db.add(session_obj)
            db.commit()
        finally:
            db.close()

        owner_list = owner_client.get("/api/sessions/blueprints/completed")
        assert owner_list.status_code == 200
        assert any(item["session_id"] == session_id for item in owner_list.json()["items"])

    with TestClient(app) as other_client:
        _register(other_client, "blueprint-other")
        other_list = other_client.get("/api/sessions/blueprints/completed")
        assert other_list.status_code == 200
        assert all(item["session_id"] != session_id for item in other_list.json()["items"])


def test_session_and_llm_profile_api_keys_are_persisted_plaintext_for_alpha_debugging():
    secret_value = "super-secret-token"

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Debug Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "llm_api_key": secret_value,
            },
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

    db = SessionLocal()
    try:
        raw_session_key = db.execute(
            text("SELECT llm_api_key FROM sessions WHERE id = :session_id"),
            {"session_id": session_id},
        ).scalar_one()
        assert raw_session_key == secret_value

        session_obj = db.query(Session).filter(Session.id == session_id).first()
        assert session_obj is not None
        assert session_obj.llm_api_key == secret_value

        profile = LlmProfile(
            profile_key=f"debug-{uuid4().hex[:8]}",
            provider="custom",
            api_url="https://example.test/v1/chat/completions",
            api_key=secret_value,
            chat_model="demo-model",
            profile_active=True,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        raw_profile_key = db.execute(
            text("SELECT api_key FROM llm_profiles WHERE id = :profile_id"),
            {"profile_id": profile.id},
        ).scalar_one()
        assert raw_profile_key == secret_value

        loaded_profile = db.query(LlmProfile).filter(LlmProfile.id == profile.id).first()
        assert loaded_profile is not None
        assert loaded_profile.api_key == secret_value
    finally:
        db.close()
