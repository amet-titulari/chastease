import json

from fastapi.testclient import TestClient
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.message import Message
from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel


def _register_admin(client: TestClient):
    email = f"dash-{uuid4().hex[:8]}@example.com"
    existing_bootstrap = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([entry for entry in [existing_bootstrap, email] if entry])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"dash-{uuid4().hex[:8]}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def _register_user_and_create_session(client: TestClient) -> int:
    email = f"lovense-{uuid4().hex[:8]}@example.com"
    existing_bootstrap = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([entry for entry in [existing_bootstrap, email] if entry])
    register_resp = client.post(
        "/auth/register",
        data={
            "username": f"lovense-{uuid4().hex[:8]}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert register_resp.status_code == 303
    setup_resp = client.post(
        "/setup/complete",
        data={
            "role_style": "structured",
            "primary_goal": "Edge 2 testen",
            "boundary_note": "Keine oeffentlichen Aufgaben",
        },
    )
    assert setup_resp.status_code == 200
    created = client.post(
        "/api/sessions",
        json={
            "persona_name": "Lovense Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    assert created.status_code == 200
    return int(created.json()["session_id"])


def test_landing_page_renders_auth_ui():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert "Willkommen im Ritualraum" in html
        assert "/auth/register" in html
        assert "/auth/login" in html


def test_dashboard_renders():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/admin/operations")
        assert resp.status_code == 200
        html = resp.text
        assert "Operations" in html
        assert "Session-Historie" in html
        assert "Vertragspruefung" in html
        assert 'id="admin-menu"' in html


def test_landing_has_no_testconsole_shortcut():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "/testconsole" not in resp.text


def test_stylesheet_contains_responsive_rules():
    with TestClient(app) as client:
        resp = client.get("/static/css/style.css")
        assert resp.status_code == 200
        assert "@media (max-width: 680px)" in resp.text
        assert "grid-template-columns: 1fr" in resp.text


def test_history_route_exists():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/history")
        assert resp.status_code == 200


def test_toys_page_includes_lovense_card_when_enabled():
    previous_enabled = settings.lovense_enabled
    previous_platform = settings.lovense_platform
    previous_token = settings.lovense_developer_token
    try:
        settings.lovense_enabled = True
        settings.lovense_platform = "Chastease"
        settings.lovense_developer_token = "dev-token"
        with TestClient(app) as client:
            session_id = _register_user_and_create_session(client)
            resp = client.get(f"/toys/{session_id}")
            assert resp.status_code == 200
            html = resp.text
            assert "Lovense Verbindung" in html
            assert 'id="dash-lovense-init"' in html
            assert "basic-sdk/core.min.js" in html
    finally:
        settings.lovense_enabled = previous_enabled
        settings.lovense_platform = previous_platform
        settings.lovense_developer_token = previous_token


def test_lovense_status_endpoint_reports_configuration():
    previous_enabled = settings.lovense_enabled
    previous_platform = settings.lovense_platform
    previous_token = settings.lovense_developer_token
    try:
        settings.lovense_enabled = True
        settings.lovense_platform = "Chastease"
        settings.lovense_developer_token = "dev-token"
        with TestClient(app) as client:
            session_id = _register_user_and_create_session(client)
            resp = client.get(f"/api/lovense/sessions/{session_id}/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enabled"] is True
            assert data["configured"] is True
            assert data["platform"] == "Chastease"
    finally:
        settings.lovense_enabled = previous_enabled
        settings.lovense_platform = previous_platform
        settings.lovense_developer_token = previous_token


def test_lovense_bootstrap_returns_server_issued_auth_token(monkeypatch):
    previous_enabled = settings.lovense_enabled
    previous_platform = settings.lovense_platform
    previous_token = settings.lovense_developer_token
    try:
        settings.lovense_enabled = True
        settings.lovense_platform = "Chastease"
        settings.lovense_developer_token = "dev-token"

        def _fake_request_lovense_auth_token(*, user, player=None):
            return {
                "enabled": True,
                "configured": True,
                "platform": "Chastease",
                "app_type": "connect",
                "sdk_url": "https://api.lovense-api.com/basic-sdk/core.min.js",
                "debug": False,
                "uid": f"chastease-user-{user.id}",
                "uname": player.nickname if player else user.username,
                "utoken": "signed",
                "auth_token": "lovense-auth-token",
            }

        monkeypatch.setattr("app.routers.lovense.request_lovense_auth_token", _fake_request_lovense_auth_token)

        with TestClient(app) as client:
            session_id = _register_user_and_create_session(client)
            resp = client.post(f"/api/lovense/sessions/{session_id}/bootstrap")
            assert resp.status_code == 200
            data = resp.json()
            assert data["auth_token"] == "lovense-auth-token"
            assert data["platform"] == "Chastease"
            assert data["app_type"] == "connect"
    finally:
        settings.lovense_enabled = previous_enabled
        settings.lovense_platform = previous_platform
        settings.lovense_developer_token = previous_token


def test_lovense_policy_roundtrip_allows_open_limits():
    with TestClient(app) as client:
        session_id = _register_user_and_create_session(client)

        save_resp = client.post(
            f"/api/lovense/sessions/{session_id}/policy",
            json={
                "min_intensity": None,
                "max_intensity": 14,
                "min_step_duration_seconds": None,
                "max_step_duration_seconds": 45,
                "min_pause_seconds": None,
                "max_pause_seconds": None,
                "max_plan_duration_seconds": None,
                "max_plan_steps": 8,
                "allow_presets": False,
                "allow_append_mode": False,
                "allowed_commands": {"vibrate": True, "pulse": True, "wave": False, "preset": False},
            },
        )
        assert save_resp.status_code == 200
        payload = save_resp.json()["policy"]
        assert payload["min_intensity"] is None
        assert payload["max_intensity"] == 14
        assert payload["max_plan_duration_seconds"] is None
        assert payload["allowed_commands"]["wave"] is False
        assert payload["allow_append_mode"] is False

        get_resp = client.get(f"/api/lovense/sessions/{session_id}/policy")
        assert get_resp.status_code == 200
        fetched = get_resp.json()["policy"]
        assert fetched == payload

        with SessionLocal() as db:
            session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
            prefs = json.loads(profile.preferences_json or "{}")
            assert prefs["toys"]["lovense_policy"]["max_step_duration_seconds"] == 45


def test_lovense_preset_library_supports_wearer_and_persona_presets():
    with TestClient(app) as client:
        session_id = _register_user_and_create_session(client)

        wearer_resp = client.post(
            f"/api/lovense/sessions/{session_id}/presets",
            json={
                "name": "Wearer Warmup",
                "command": "preset",
                "preset": "tease_ramp",
                "duration_seconds": 20,
                "loops": 1,
            },
        )
        assert wearer_resp.status_code == 200

        persona_resp = client.post(
            f"/api/lovense/sessions/{session_id}/persona-presets",
            json={
                "name": "Persona Pattern",
                "command": "pattern",
                "pattern": "3;6;9;6;3;0",
                "duration_seconds": 18,
                "interval": 180,
            },
        )
        assert persona_resp.status_code == 200

        library = client.get(f"/api/lovense/sessions/{session_id}/preset-library")
        assert library.status_code == 200
        payload = library.json()["library"]
        assert any(item["key"] == "wearer_warmup" for item in payload["wearer"])
        assert any(item["key"] == "persona_pattern" for item in payload["persona"])
        assert any(item["key"] == "tease_ramp" for item in payload["builtin"])
        assert any(item["key"] == "wearer_warmup" for item in payload["combined"])
        assert any(item["key"] == "persona_pattern" for item in payload["combined"])


def test_lovense_event_endpoint_persists_session_event_message():
    with TestClient(app) as client:
        session_id = _register_user_and_create_session(client)

        resp = client.post(
            f"/api/lovense/sessions/{session_id}/events",
            json={
                "source": "manual",
                "phase": "executed",
                "command": "preset",
                "title": "Warmup",
                "preset": "tease_ramp",
            },
        )
        assert resp.status_code == 200

        with SessionLocal() as db:
            rows = db.query(Message).filter(Message.session_id == session_id).all()
            assert any("Toy executed: Warmup (tease_ramp)" in str(item.content) for item in rows)


def test_session_detail_exposes_phase_progress_snapshot():
    with TestClient(app) as client:
        session_id = _register_user_and_create_session(client)

        with SessionLocal() as db:
            session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
            prefs = json.loads(profile.preferences_json or "{}")
            prefs["scenario_preset"] = "ametara_titulari_devotion_protocol"
            prefs["scenario_phase_id"] = "phase_3"
            prefs["scenario_phase_progress"] = 1
            profile.preferences_json = json.dumps(prefs)
            session_obj.relationship_state_json = json.dumps(
                {
                    "trust": 86,
                    "obedience": 83,
                    "resistance": 4,
                    "favor": 80,
                    "strictness": 90,
                    "frustration": 88,
                    "attachment": 84,
                }
            )
            session_obj.phase_state_json = json.dumps(
                {
                    "phase_id": "phase_3",
                    "phase_index": 3,
                    "started_at": "2026-03-30T12:00:00+00:00",
                    "targets": {
                        "trust": 6,
                        "obedience": 8,
                        "resistance": 5,
                        "favor": 5,
                        "strictness": 5,
                        "frustration": 6,
                        "attachment": 5,
                    },
                    "scores": {
                        "trust": 6,
                        "obedience": 4,
                        "resistance": 1,
                        "favor": 5,
                        "strictness": 5,
                        "frustration": 3,
                        "attachment": 5,
                    },
                }
            )
            db.add(profile)
            db.add(session_obj)
            db.commit()

        resp = client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        payload = resp.json()["phase_progress"]
        assert payload["phase_index"] == 3
        assert payload["score_count"] == 4
        assert payload["target_score_count"] == 7
        resistance = next(item for item in payload["metrics"] if item["key"] == "resistance")
        assert resistance["goal_value"] == 5
        assert resistance["progress_total"] == 5


def test_toys_page_exposes_simulator_flag():
    previous_simulator = settings.lovense_simulator_enabled
    try:
        settings.lovense_simulator_enabled = True
        with TestClient(app) as client:
            session_id = _register_user_and_create_session(client)
            resp = client.get(f"/toys/{session_id}")
            assert resp.status_code == 200
            assert 'data-lovense-simulator="1"' in resp.text
    finally:
        settings.lovense_simulator_enabled = previous_simulator
