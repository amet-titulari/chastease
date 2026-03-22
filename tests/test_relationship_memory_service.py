from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.player_profile import PlayerProfile
from app.models.session import Session
from app.services.relationship_memory import build_relationship_memory


def _create_session(client: TestClient, persona_name: str, player_name: str) -> int:
    resp = client.post(
        "/api/sessions",
        json={
            "persona_name": persona_name,
            "player_nickname": player_name,
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
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


def test_relationship_memory_summarizes_completed_sessions_for_same_user():
    with TestClient(app) as client:
        completed_session_id = _create_session(client, "Template Persona", "Template Wearer")
        current_session_id = _create_session(client, "Template Persona", "Template Wearer")

        with SessionLocal() as db:
            completed_row = db.query(Session).filter(Session.id == completed_session_id).first()
            current_row = db.query(Session).filter(Session.id == current_session_id).first()
            completed_profile = db.query(PlayerProfile).filter(PlayerProfile.id == completed_row.player_profile_id).first()
            current_profile = db.query(PlayerProfile).filter(PlayerProfile.id == current_row.player_profile_id).first()

            completed_profile.auth_user_id = 999
            current_profile.auth_user_id = 999
            completed_row.relationship_state_json = '{"trust": 91, "obedience": 74, "resistance": 12, "attachment": 57, "control_level": "punitive"}'
            completed_row.status = "completed"
            completed_row.lock_end_actual = datetime.now(timezone.utc)

            db.add(completed_profile)
            db.add(current_profile)
            db.add(completed_row)
            db.commit()

            db.refresh(current_row)
            memory = build_relationship_memory(db, current_row)

        assert memory["sessions_considered"] == 1
        assert memory["dominant_control_level"] == "punitive"
        assert memory["metrics"]["trust"]["latest_score"] == 91
        assert memory["metrics"]["trust"]["average_delta"] == 36
        assert memory["metrics"]["resistance"]["latest_delta"] == -8
        assert memory["summary"]
        assert memory["highlights"]
