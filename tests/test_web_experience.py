from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.auth_user import AuthUser
from app.models.session import Session as SessionModel


def _register_and_finish_setup(client: TestClient, email: str = "xp-user@example.com"):
    username = f"xp-{uuid4().hex[:8]}"
    unique_email = email if email != "xp-user@example.com" else f"xp-{uuid4().hex[:8]}@example.com"
    existing_bootstrap = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([entry for entry in [existing_bootstrap, unique_email] if entry])

    register_resp = client.post(
        "/auth/register",
        data={
            "username": username,
            "email": unique_email,
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
            "primary_goal": "Play",
            "boundary_note": "No work hours",
        },
    )
    assert setup_resp.status_code == 200


def test_experience_page_renders():
    with TestClient(app) as client:
        _register_and_finish_setup(client)
        resp = client.get("/experience")
        assert resp.status_code == 200
        html = resp.text
        assert "Chastease Chat" in html
        assert "Onboarding" in html
        assert "Wearer" in html
        assert "xp-create-session" in html
        assert "xp-scenario-preset" in html
        assert "xp-scenario-editor" in html
        assert "xp-se-save-btn" in html
        assert "xp-sign-contract" in html
        assert "xp-contract-preview" in html
        assert "xp-contract-goal" in html
        assert "xp-contract-touch-rules" in html
        assert "xp-quick-start" in html
        assert "xp-gate-quick" in html


def test_contract_view_uses_authenticated_main_menu():
    with TestClient(app) as client:
        _register_and_finish_setup(client)
        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Menu Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        signed = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert signed.status_code == 200

        resp = client.get(f"/contract/{session_id}")
        assert resp.status_code == 200
        html = resp.text
        assert ">Chat<" in html
        assert ">Dashboard<" in html
        assert ">Games<" in html


def test_experience_assets_are_served():
    with TestClient(app) as client:
        js = client.get("/static/js/experience.js")
        assert js.status_code == 200
        assert "xp-create-session" in js.text
        assert "xpLoadScenarioPresets" in js.text
        assert "xpSaveScenarioEditor" in js.text
        assert "sign-contract" in js.text
        assert "xpSwitchStep(6)" in js.text
        assert "xpApplyQuickStart" in js.text


def test_experience_onboarding_allows_persona_and_scenario_crud_for_normal_user():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        persona_resp = client.post(
            "/api/personas",
            json={
                "name": "Onboarding Persona",
                "speech_style_tone": "warm",
                "speech_style_dominance": "gentle-dominant",
                "strictness_level": 3,
                "description": "Inline erstellt",
                "system_prompt": "Bleib praesent.",
                "avatar_media_id": None,
            },
        )
        assert persona_resp.status_code == 200
        persona_id = persona_resp.json()["id"]

        persona_update = client.put(
            f"/api/personas/{persona_id}",
            json={
                "name": "Onboarding Persona Plus",
                "speech_style_tone": "direct",
            },
        )
        assert persona_update.status_code == 200
        assert persona_update.json()["name"] == "Onboarding Persona Plus"

        scenario_resp = client.post(
            "/api/scenarios",
            json={
                "title": "Onboarding Scenario",
                "key": f"onboarding_{uuid4().hex[:8]}",
                "summary": "Wird direkt im Setup gepflegt.",
                "tags": ["ritual", "focus"],
                "phases": [],
                "lorebook": [],
            },
        )
        assert scenario_resp.status_code == 200
        scenario_id = scenario_resp.json()["id"]

        scenario_update = client.put(
            f"/api/scenarios/{scenario_id}",
            json={
                "title": "Onboarding Scenario Plus",
                "summary": "Aktualisiert durch normalen Nutzer.",
                "tags": ["ritual", "adapted"],
            },
        )
        assert scenario_update.status_code == 200
        assert scenario_update.json()["title"] == "Onboarding Scenario Plus"

        # play.js handles the live chat/task/regenerate functionality
        play_js = client.get("/static/js/play.js")
        assert play_js.status_code == 200
        assert "play-safety-yellow" in play_js.text
        assert "play-ops-banner" in play_js.text
        assert "/api/sessions/${SESSION_ID}/messages" in play_js.text

        dashboard_js = client.get("/static/js/dashboard.js")
        assert dashboard_js.status_code == 200
        assert "dashLoadRunHistory" in dashboard_js.text
        assert "dash-hygiene-open" in dashboard_js.text

        css = client.get("/static/css/experience.css")
        assert css.status_code == 200
        assert "xp-grid" in css.text
        assert "chat-timeline" in css.text
        assert "xp-quickbar" in css.text

        dashboard_css = client.get("/static/css/dashboard.css")
        assert dashboard_css.status_code == 200
        assert "dash-grid" in dashboard_css.text
        assert "dash-run-card" in dashboard_css.text


def test_experience_draft_autosave_updates_profile_defaults():
    with TestClient(app) as client:
        _register_and_finish_setup(client)
        res = client.post(
            "/api/experience/draft",
            json={
                "wearer_nickname": "Nova",
                "experience_level": "advanced",
                "hard_limits": "humiliation, pain",
                "contract_goal": "Klare Fuehrung und einvernehmliche Enthaltsamkeit.",
                "contract_method": "psychologische Keuschhaltung",
                "penalty_multiplier": 1.7,
                "gentle_mode": True,
                "hygiene_opening_max_duration_seconds": 720,
                "llm_provider": "custom",
                "llm_api_url": "https://example.test/v1/chat/completions",
                "llm_chat_model": "grok-test",
                "llm_vision_model": "grok-vision-test",
            },
        )
        assert res.status_code == 200
        assert res.json().get("ok") is True

        profile = client.get("/api/settings/summary")
        assert profile.status_code == 200
        body = profile.json()
        assert body["experience_level"] == "advanced"
        assert body["boundary"] == "humiliation, pain"
        llm = body.get("llm") or {}
        assert llm.get("provider") == "custom"
        assert llm.get("chat_model") == "grok-test"


def test_experience_draft_updates_active_session_player_and_hygiene_max():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Test Persona",
                "player_nickname": "eritque",
                "min_duration_seconds": 3600,
                "hygiene_opening_max_duration_seconds": 900,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        signed = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert signed.status_code == 200
        assert signed.json().get("status") == "active"

        play = client.get(f"/play/{session_id}", follow_redirects=False)
        assert play.status_code == 200

        draft = client.post(
            "/api/experience/draft",
            json={
                "persona_name": "Esmeralda",
                "persona_tone": "precise",
                "persona_dominance": "firm",
                "persona_description": "Updated persona",
                "persona_system_prompt": "Stay strict and clear",
                "scenario_preset": "ametara_titulari_devotion_protocol",
                "wearer_nickname": "Esmeralda",
                "experience_level": "advanced",
                "hard_limits": "running, humiliation",
                "min_duration_seconds": 7200,
                "max_duration_seconds": 28800,
                "hygiene_limit_daily": 3,
                "hygiene_limit_weekly": 8,
                "hygiene_limit_monthly": 20,
                "penalty_multiplier": 1.4,
                "default_penalty_seconds": 5400,
                "max_penalty_seconds": 21600,
                "gentle_mode": True,
                "hygiene_opening_max_duration_seconds": 720,
                "seal_enabled": True,
                "initial_seal_number": "S-987",
                "llm_provider": "custom",
                "llm_api_url": "https://example.test/v1/chat/completions",
                "llm_chat_model": "grok-sync",
                "llm_vision_model": "grok-vision-sync",
                "llm_active": True,
            },
        )
        assert draft.status_code == 200

        summary = client.get(f"/api/settings/summary?session_id={session_id}")
        assert summary.status_code == 200
        data = summary.json()
        assert data["session"]["persona_name"] == "Esmeralda"


def test_draft_session_can_be_updated_without_creating_new_session():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Draft Persona",
                "player_nickname": "Nova",
                "min_duration_seconds": 3600,
                "max_duration_seconds": 7200,
                "contract_goal": "Erste Fassung.",
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        updated = client.put(
            f"/api/sessions/{session_id}/draft",
            json={
                "persona_name": "Draft Persona",
                "player_nickname": "Nova",
                "min_duration_seconds": 3600,
                "max_duration_seconds": 10800,
                "contract_goal": "Nachgeschaerfte verbindliche Fassung.",
                "contract_touch_rules": "Keine Beruehrung ohne Erlaubnis.",
                "scenario_preset": "ametara_titulari_devotion_protocol",
                "hard_limits": ["public play"],
                "llm_active": True,
            },
        )
        assert updated.status_code == 200
        payload = updated.json()
        assert payload["session_id"] == session_id
        assert payload["updated"] is True
        assert "Nachgeschaerfte verbindliche Fassung." in payload["contract_preview"]
        assert "Keine Beruehrung ohne Erlaubnis." in payload["contract_preview"]

        detail = client.get(f"/api/sessions/{session_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "draft"


def test_experience_and_profile_redirect_to_play_when_active_session_exists():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Redirect Persona",
                "player_nickname": "Redirect Player",
                "min_duration_seconds": 900,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        signed = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert signed.status_code == 200
        assert signed.json().get("status") == "active"

        play = client.get(f"/play/{session_id}", follow_redirects=False)
        assert play.status_code == 200

        experience = client.get("/experience", follow_redirects=False)
        assert experience.status_code == 303
        assert experience.headers.get("location") == f"/play/{session_id}"

        profile = client.get("/profile", follow_redirects=False)
        assert profile.status_code == 200
        assert "Audio und Sprache" in profile.text
        assert "Zur laufenden Session" in profile.text
        assert "Session-Uebersicht" in profile.text
        assert "Wearer-Profil" in profile.text
        assert "Dein Wearer-Profil" in profile.text
        assert 'hx-get="/profile/partials/session-summary"' in profile.text


def test_play_page_uses_versioned_play_script_url():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Cache Persona",
                "player_nickname": "Cache Player",
                "min_duration_seconds": 900,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        signed = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert signed.status_code == 200

        play = client.get(f"/play/{session_id}", follow_redirects=False)
        assert play.status_code == 200
        assert '/static/js/play.js?v=' in play.text
        assert 'href="/dashboard/' in play.text
        assert 'id="play-focus-toggle"' in play.text
        assert 'data-app-version="0.4.0"' in play.text
        assert "Regenerate" not in play.text
        assert "Verlauf" not in play.text


def test_dashboard_page_renders_for_active_session():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Dashboard Persona",
                "player_nickname": "Dashboard Player",
                "min_duration_seconds": 900,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        signed = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert signed.status_code == 200

        dashboard = client.get(f"/dashboard/{session_id}", follow_redirects=False)
        assert dashboard.status_code == 200
        assert "Spieler-Dashboard" in dashboard.text
        assert "Spiele und Resultate" in dashboard.text
        assert '/static/js/dashboard.js?v=' in dashboard.text

        nav = client.get(f"/play/{session_id}", follow_redirects=False)
        assert nav.status_code == 200
        assert ">Chat<" in nav.text
        assert ">Dashboard<" in nav.text


def test_settings_summary_includes_total_played_duration_across_owned_sessions():
    with TestClient(app) as client:
        email = f"xp-total-{uuid4().hex[:8]}@example.com"
        _register_and_finish_setup(client, email=email)

        first = client.post(
            "/api/sessions",
            json={
                "persona_name": "Total Persona One",
                "player_nickname": "Player One",
                "min_duration_seconds": 3600,
            },
        )
        assert first.status_code == 200
        first_session_id = first.json()["session_id"]

        second = client.post(
            "/api/sessions",
            json={
                "persona_name": "Total Persona Two",
                "player_nickname": "Player Two",
                "min_duration_seconds": 3600,
            },
        )
        assert second.status_code == 200
        second_session_id = second.json()["session_id"]

        db = SessionLocal()
        try:
            user = db.query(AuthUser).filter(AuthUser.email == email).first()
            assert user is not None

            first_session = db.query(SessionModel).filter(SessionModel.id == first_session_id).first()
            second_session = db.query(SessionModel).filter(SessionModel.id == second_session_id).first()
            assert first_session is not None
            assert second_session is not None

            first_session.lock_start = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
            first_session.lock_end_actual = first_session.lock_start + timedelta(hours=10)
            second_session.lock_start = datetime(2026, 3, 3, 9, 30, 0, tzinfo=timezone.utc)
            second_session.lock_end_actual = second_session.lock_start + timedelta(hours=26, minutes=15)
            user.active_session_id = second_session_id

            db.add(first_session)
            db.add(second_session)
            db.add(user)
            db.commit()
        finally:
            db.close()

        summary = client.get(f"/api/settings/summary?session_id={second_session_id}")
        assert summary.status_code == 200
        payload = summary.json()
        session_payload = payload.get("session") or {}
        assert session_payload.get("total_played_seconds") == (10 * 3600) + (26 * 3600) + (15 * 60)


def test_games_page_renders_game_cards_and_current_session_entrypoint():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Game Persona",
                "player_nickname": "Game Player",
                "min_duration_seconds": 900,
            },
        )
        assert created.status_code == 200

        resp = client.get("/games")
        assert resp.status_code == 200
        html = resp.text
        assert "Spiele" in html
        assert "Aktuelle Session" in html
        assert "Posture Training" in html
        assert "Spiel oeffnen" in html
        assert "Schwellwerte" not in html
        assert "Postures verwalten" not in html
        assert 'id="admin-menu"' in html
        assert "/game/" in html


def test_games_postures_management_page_renders():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        resp = client.get("/games/postures?module_key=posture_training")
        assert resp.status_code == 200
        html = resp.text
        assert "Postures verwalten" in html
        assert "ZIP importieren (ersetzt alle)" in html
        assert "Alle Postures als ZIP exportieren" in html


def test_admin_center_page_renders():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        resp = client.get("/admin")
        assert resp.status_code == 200
        html = resp.text
        assert "Admin Center" in html
        assert 'id="admin-menu"' in html
        assert "Posture Library" in html
        assert "/admin/postures/matrix" in html
        assert "/admin/operations" in html
        assert "Personas" in html
        assert "Scenarios" in html
        assert "Inventar" in html


def test_admin_posture_matrix_page_renders():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        resp = client.get("/admin/postures/matrix")
        assert resp.status_code == 200
        html = resp.text
        assert "Posture Matrix" in html
        assert 'id="admin-menu"' in html
        assert "Matrix speichern" in html
        assert "Sichtbare im Modul aktivieren" in html
        assert "Suche" in html
        assert "/api/inventory/postures/matrix" in html


def test_admin_operations_page_renders():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        resp = client.get("/admin/operations")
        assert resp.status_code == 200
        html = resp.text
        assert "Operations" in html
        assert 'id="admin-menu"' in html
        assert "Session-Historie" in html
        assert "Vertragspruefung" in html


def test_game_page_prefills_setup_from_latest_run_values():
    with TestClient(app) as client:
        _register_and_finish_setup(client)

        created = client.post(
            "/api/sessions",
            json={
                "persona_name": "Game Persona",
                "player_nickname": "Game Player",
                "min_duration_seconds": 900,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        started = client.post(
            f"/api/games/sessions/{session_id}/runs/start",
            json={
                "module_key": "posture_training",
                "difficulty": "hard",
                "duration_minutes": 17,
                "transition_seconds": 11,
                "max_misses_before_penalty": 4,
                "session_penalty_seconds": 86400,
            },
        )
        assert started.status_code == 200

        resp = client.get(f"/game/{session_id}?module_key=posture_training")
        assert resp.status_code == 200
        html = resp.text

        assert 'id="gm-duration" type="number" min="1" max="240" value="17"' in html
        assert 'id="gm-transition-seconds" type="number" min="0" max="60" value="11"' in html
        assert 'id="gm-max-misses" type="number" min="1" max="20" value="4"' in html
        assert 'id="gm-session-penalty-days" type="number" min="0" max="365" value="1"' in html
        assert 'id="gm-session-penalty-hours" type="number" min="0" max="23" value="0"' in html
        assert 'id="gm-session-penalty-minutes" type="number" min="0" max="59" value="0"' in html
        assert 'const initialDifficulty = "hard";' in html
