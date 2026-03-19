from fastapi.testclient import TestClient
from uuid import uuid4

from app.database import SessionLocal
from app.main import app
from app.models.auth_user import AuthUser
from app.models.llm_profile import LlmProfile
from app.models.player_profile import PlayerProfile
from app.services.auth_password import is_legacy_password_hash, legacy_hash_password


def _register(client: TestClient, email: str = "setup-user@example.com"):
    username = f"setup-{uuid4().hex[:8]}"
    unique_email = email if email != "setup-user@example.com" else f"setup-{uuid4().hex[:8]}@example.com"
    return client.post(
        "/auth/register",
        data={
            "username": username,
            "email": unique_email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )


def test_register_redirects_to_experience():
    with TestClient(app) as client:
        register_resp = _register(client)
        assert register_resp.status_code == 303
        assert register_resp.headers["location"] == "/experience"

        experience_resp = client.get("/experience")
        assert experience_resp.status_code == 200
        assert "Onboarding" in experience_resp.text


def test_register_stores_modern_password_hash():
    with TestClient(app) as client:
        email = f"hash-{uuid4().hex[:8]}@example.com"
        register_resp = _register(client, email=email)
        assert register_resp.status_code == 303

        db = SessionLocal()
        try:
            user = db.query(AuthUser).filter(AuthUser.email == email).first()
            assert user is not None
            assert user.password_hash.startswith("$argon2")
            assert user.password_salt == ""
            assert is_legacy_password_hash(user.password_hash) is False
        finally:
            db.close()


def test_setup_completion_redirects_to_experience():
    with TestClient(app) as client:
        register_resp = _register(client, email=f"complete-{uuid4().hex[:8]}@example.com")
        assert register_resp.status_code == 303
        finish_resp = client.post(
            "/setup/complete",
            data={
                "role_style": "structured",
                "primary_goal": "Mehr Konsistenz",
                "boundary_note": "Keine Aufgaben waehrend Meetings",
                "wearer_nickname": "Eri",
                "hard_limits": "kein pain, keine public tasks",
                "penalty_multiplier": "1.3",
                "gentle_mode": "true",
            },
            follow_redirects=False,
        )
        assert finish_resp.status_code == 303
        assert finish_resp.headers["location"] == "/experience"

        experience_resp = client.get("/experience")
        assert experience_resp.status_code == 200
        assert "value=\"Eri\"" in experience_resp.text
        assert "value=\"1.3\"" in experience_resp.text

        summary = client.get("/api/settings/summary")
        assert summary.status_code == 200
        payload = summary.json()
        assert "kein pain, keine public tasks" in str(payload.get("boundary") or "")


def test_login_for_incomplete_setup_redirects_to_experience():
    with TestClient(app) as client:
        email = f"login-{uuid4().hex[:8]}@example.com"
        register_resp = _register(client, email=email)
        assert register_resp.status_code == 303
        client.post("/auth/logout")

        login_resp = client.post(
            "/auth/login",
            data={"email": email, "password": "verysecure1"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        assert login_resp.headers["location"] == "/experience"


def test_login_upgrades_legacy_password_hash_to_modern_hash():
    with TestClient(app) as client:
        email = f"legacy-{uuid4().hex[:8]}@example.com"
        register_resp = _register(client, email=email)
        assert register_resp.status_code == 303

        db = SessionLocal()
        try:
            user = db.query(AuthUser).filter(AuthUser.email == email).first()
            assert user is not None
            user.password_salt = "legacy-salt"
            user.password_hash = legacy_hash_password("verysecure1", user.password_salt)
            user.session_token = None
            db.add(user)
            db.commit()
        finally:
            db.close()

        login_resp = client.post(
            "/auth/login",
            data={"email": email, "password": "verysecure1"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303

        db = SessionLocal()
        try:
            user = db.query(AuthUser).filter(AuthUser.email == email).first()
            assert user is not None
            assert user.password_hash.startswith("$argon2")
            assert user.password_salt == ""
            assert user.session_token
        finally:
            db.close()


def test_experience_redirects_to_landing_when_logged_out():
    with TestClient(app) as client:
        resp = client.get("/experience", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"


def test_profile_requires_authentication():
    with TestClient(app) as client:
        resp = client.get("/profile", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"


def test_inventory_page_requires_authentication():
    with TestClient(app) as client:
        resp = client.get("/inventory", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"


def test_profile_can_update_setup_data():
    with TestClient(app) as client:
        email = f"profile-update-{uuid4().hex[:8]}@example.com"
        register_resp = _register(client, email=email)
        assert register_resp.status_code == 303

        client.post(
            "/setup/complete",
            data={
                "role_style": "strict",
                "primary_goal": "Original Ziel",
                "boundary_note": "Original Grenze",
            },
        )

        update_resp = client.post(
            "/profile/setup",
            data={
                "role_style": "supportive",
                "primary_goal": "Neues Ziel",
                "boundary_note": "Neue Grenze",
                "wearer_nickname": "Neo",
                "hard_limits": "kein sleep deprivation",
                "penalty_multiplier": "0.8",
                "gentle_mode": "true",
            },
        )
        assert update_resp.status_code == 200
        assert "Setup-Daten wurden aktualisiert." in update_resp.text
        assert "Neues Ziel" in update_resp.text
        assert "value=\"Neo\"" in update_resp.text
        assert "kein sleep deprivation" in update_resp.text

        db = SessionLocal()
        try:
            user = db.query(AuthUser).filter(AuthUser.email == email).first()
            assert user is not None
            assert user.default_player_profile_id is not None
            profile = db.query(PlayerProfile).filter(PlayerProfile.id == user.default_player_profile_id).first()
            assert profile is not None
            assert profile.auth_user_id == user.id
            assert profile.nickname == "Neo"
            assert profile.experience_level == "beginner"
        finally:
            db.close()


def test_profile_page_renders_audio_gateway_section():
    with TestClient(app) as client:
        register_resp = _register(client, email=f"profile-page-{uuid4().hex[:8]}@example.com")
        assert register_resp.status_code == 303

        resp = client.get("/profile", follow_redirects=False)
        assert resp.status_code == 200
        assert "Audio Gateway" in resp.text
        assert "/profile/audio" in resp.text
        assert "/profile/audio/test" in resp.text
        assert "Voice Modus" not in resp.text
        assert "Voice Agent ID" not in resp.text
        assert "https://unpkg.com/htmx.org@1.9.12" in resp.text
        assert 'hx-get="/profile/partials/session-summary"' in resp.text


def test_profile_session_summary_partial_renders_for_authenticated_user():
    with TestClient(app) as client:
        register_resp = _register(client, email=f"profile-partial-{uuid4().hex[:8]}@example.com")
        assert register_resp.status_code == 303

        resp = client.get("/profile/partials/session-summary", follow_redirects=False)
        assert resp.status_code == 200
        assert "Session-Uebersicht" in resp.text
        assert 'hx-trigger="load, every 30s"' in resp.text


def test_profile_audio_test_requires_authentication():
    with TestClient(app) as client:
        resp = client.post("/profile/audio/test")
        assert resp.status_code == 401
        assert resp.json()["ok"] is False


def test_cross_origin_profile_update_is_rejected_by_csrf_protection():
    with TestClient(app) as client:
        register_resp = _register(client, email=f"csrf-{uuid4().hex[:8]}@example.com")
        assert register_resp.status_code == 303

        resp = client.post(
            "/profile/setup",
            data={
                "role_style": "supportive",
                "primary_goal": "CSRF Test",
                "boundary_note": "Keine Cross-Origin Requests",
            },
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "csrf_failed"


def test_profile_llm_falls_back_to_active_session_config_when_default_missing():
    with TestClient(app) as client:
        register_resp = _register(client, email=f"profile-llm-fallback-{uuid4().hex[:8]}@example.com")
        assert register_resp.status_code == 303

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Fallback Persona",
                "player_nickname": "Fallback Player",
                "min_duration_seconds": 900,
                "llm_provider": "custom",
                "llm_api_url": "https://example.test/v1/chat/completions",
                "llm_chat_model": "grok-session",
                "llm_vision_model": "grok-vision-session",
                "llm_active": True,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        play = client.get(f"/play/{session_id}", follow_redirects=False)
        assert play.status_code == 200

        db = SessionLocal()
        try:
            db.query(LlmProfile).filter(LlmProfile.profile_key == "default").delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

        profile = client.get("/profile", follow_redirects=False)
        assert profile.status_code == 200
        assert "https://example.test/v1/chat/completions" in profile.text
        assert "grok-session" in profile.text


def test_profile_can_restart_setup_flow():
    with TestClient(app) as client:
        register_resp = _register(client, email=f"profile-restart-{uuid4().hex[:8]}@example.com")
        assert register_resp.status_code == 303

        client.post(
            "/setup/complete",
            data={
                "role_style": "structured",
                "primary_goal": "Routine",
                "boundary_note": "Keine Nachtaufgaben",
            },
        )

        restart_resp = client.post("/profile/restart-setup", follow_redirects=False)
        assert restart_resp.status_code == 303
        assert restart_resp.headers["location"] == "/experience"

        experience_resp = client.get("/experience", follow_redirects=False)
        assert experience_resp.status_code == 200
