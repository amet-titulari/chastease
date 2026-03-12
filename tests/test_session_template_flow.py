from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.session import Session


def _create_base_session(client: TestClient) -> int:
    resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Template Persona",
            "player_nickname": "Template Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
            "hygiene_limit_daily": 1,
            "hygiene_limit_weekly": 2,
            "hygiene_limit_monthly": 7,
            "experience_level": "intermediate",
            "scenario_preset": "amet_titulari_devotion_protocol",
            "llm_provider": "custom",
            "llm_api_url": "https://api.example.com/v1/chat/completions",
            "llm_chat_model": "grok-test",
            "llm_vision_model": "grok-test-vision",
            "llm_active": True,
        },
    )
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_session_stores_llm_profile_snapshot():
    with TestClient(app) as client:
        session_id = _create_base_session(client)
        detail = client.get(f"/api/sessions/{session_id}")
        assert detail.status_code == 200
        llm = detail.json()["llm_session"]
        assert llm["provider"] == "custom"
        assert llm["chat_model"] == "grok-test"
        assert llm["active"] is True


def test_completed_session_can_be_used_as_blueprint():
    with TestClient(app) as client:
        template_id = _create_base_session(client)

        with SessionLocal() as db:
            row = db.query(Session).filter(Session.id == template_id).first()
            row.status = "completed"
            row.lock_end_actual = datetime.now(timezone.utc)
            db.add(row)
            db.commit()

        listing = client.get("/api/sessions/blueprints/completed")
        assert listing.status_code == 200
        assert any(item["session_id"] == template_id for item in listing.json()["items"])

        blueprint = client.get(f"/api/sessions/blueprints/{template_id}")
        assert blueprint.status_code == 200
        payload = blueprint.json()
        assert payload["persona_name"] == "Template Persona"
        assert payload["player_nickname"] == "Template Wearer"

        cloned = client.post(
            "/api/sessions",
            json={
                "template_session_id": template_id,
            },
        )
        assert cloned.status_code == 200
        new_session_id = cloned.json()["session_id"]

        new_detail = client.get(f"/api/sessions/{new_session_id}")
        assert new_detail.status_code == 200
        assert new_detail.json()["min_duration_seconds"] == 300
        assert new_detail.json()["llm_session"]["provider"] == "custom"
