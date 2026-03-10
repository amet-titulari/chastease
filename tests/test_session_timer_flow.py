from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.session import Session


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Timer Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_timer_add_remove_and_status():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        before = client.get(f"/api/sessions/{session_id}/timer").json()["remaining_seconds"]

        add_resp = client.post(f"/api/sessions/{session_id}/timer/add", json={"seconds": 120})
        assert add_resp.status_code == 200

        after_add = client.get(f"/api/sessions/{session_id}/timer").json()["remaining_seconds"]
        assert after_add >= before + 115

        remove_resp = client.post(f"/api/sessions/{session_id}/timer/remove", json={"seconds": 60})
        assert remove_resp.status_code == 200

        after_remove = client.get(f"/api/sessions/{session_id}/timer").json()["remaining_seconds"]
        assert after_remove <= after_add - 55


def test_timer_freeze_and_unfreeze_extends_lock_end():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        freeze_resp = client.post(f"/api/sessions/{session_id}/timer/freeze")
        assert freeze_resp.status_code == 200
        assert freeze_resp.json()["timer_frozen"] is True

        with SessionLocal() as db:
            row = db.query(Session).filter(Session.id == session_id).first()
            lock_end_before = row.lock_end
            row.freeze_start = datetime.now(timezone.utc) - timedelta(seconds=120)
            db.add(row)
            db.commit()

        unfreeze_resp = client.post(f"/api/sessions/{session_id}/timer/unfreeze")
        assert unfreeze_resp.status_code == 200
        assert unfreeze_resp.json()["timer_frozen"] is False

        with SessionLocal() as db:
            row = db.query(Session).filter(Session.id == session_id).first()
            assert row.lock_end >= lock_end_before + timedelta(seconds=115)
