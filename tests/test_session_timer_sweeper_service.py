from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.message import Message
from app.models.session import Session
from app.services.session_timer_sweeper import sweep_expired_active_sessions


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Sweep Timer Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_sweeper_completes_expired_active_sessions_and_logs_event():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        with SessionLocal() as db:
            row = db.query(Session).filter(Session.id == session_id).first()
            row.lock_end = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.add(row)
            db.commit()

        result = sweep_expired_active_sessions()
        assert result["scanned_sessions"] >= 1
        assert result["ended_sessions"] >= 1

        with SessionLocal() as db:
            row = db.query(Session).filter(Session.id == session_id).first()
            assert row.status == "completed"
            assert row.lock_end_actual is not None

            event = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.message_type == "session_event")
                .order_by(Message.id.desc())
                .first()
            )
            assert event is not None
            assert "automatisch beendet" in event.content
