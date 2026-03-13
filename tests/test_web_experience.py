from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _register_and_finish_setup(client: TestClient, email: str = "xp-user@example.com"):
    username = f"xp-{uuid4().hex[:8]}"
    unique_email = email if email != "xp-user@example.com" else f"xp-{uuid4().hex[:8]}@example.com"

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
        assert "Onboarding" in html
        assert "xp-create-session" in html
        assert "xp-scenario-preset" in html
        assert "xp-sign-contract" in html
        assert "xp-contract-preview" in html


def test_experience_assets_are_served():
    with TestClient(app) as client:
        js = client.get("/static/js/experience.js")
        assert js.status_code == 200
        assert "xp-create-session" in js.text
        assert "xpLoadScenarioPresets" in js.text
        assert "sign-contract" in js.text
        assert "xpSwitchStep(6)" in js.text

        # play.js handles the live chat/task/regenerate functionality
        play_js = client.get("/static/js/play.js")
        assert play_js.status_code == 200
        assert "messages/regenerate" in play_js.text
        assert "play-safety-yellow" in play_js.text

        css = client.get("/static/css/experience.css")
        assert css.status_code == 200
        assert "xp-grid" in css.text
        assert "chat-timeline" in css.text


def test_experience_draft_autosave_updates_profile_defaults():
    with TestClient(app) as client:
        _register_and_finish_setup(client)
        res = client.post(
            "/api/experience/draft",
            json={
                "wearer_nickname": "Nova",
                "experience_level": "advanced",
                "hard_limits": "humiliation, pain",
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
        assert data["session"]["player_nickname"] == "Esmeralda"
        assert data["session"]["min_duration_seconds"] == 7200
        assert data["session"]["max_duration_seconds"] == 28800
        assert data["session"]["hygiene_limit_daily"] == 3
        assert data["session"]["hygiene_limit_weekly"] == 8
        assert data["session"]["hygiene_limit_monthly"] == 20
        assert data["session"]["hygiene_opening_max_duration_seconds"] == 720
        assert data["session"]["active_seal_number"] == "S-987"
        assert (data.get("llm") or {}).get("chat_model") == "grok-sync"

        session_detail = client.get(f"/api/sessions/{session_id}")
        assert session_detail.status_code == 200
        player_profile = session_detail.json().get("player_profile") or {}
        assert player_profile.get("experience_level") == "advanced"
        assert player_profile.get("hard_limits") == ["running", "humiliation"]
        prefs = player_profile.get("preferences") or {}
        assert prefs.get("scenario_preset") == "ametara_titulari_devotion_protocol"
        reaction = player_profile.get("reaction_patterns") or {}
        assert reaction.get("penalty_multiplier") == 1.4
        assert reaction.get("default_penalty_seconds") == 5400
        assert reaction.get("max_penalty_seconds") == 21600
