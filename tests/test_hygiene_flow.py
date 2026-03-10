from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.hygiene_opening import HygieneOpening
from app.main import app


def test_hygiene_opening_request_and_relock():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "KH",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 600,
            },
        )
        session_id = create_resp.json()["session_id"]

        sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert sign_resp.status_code == 200

        open_resp = client.post(
            f"/api/sessions/{session_id}/hygiene/openings",
            json={"duration_seconds": 120, "old_seal_number": "A-1"},
        )
        assert open_resp.status_code == 200
        opening = open_resp.json()
        assert opening["status"] == "active"

        status_resp = client.get(f"/api/sessions/{session_id}/hygiene/openings/{opening['opening_id']}")
        assert status_resp.status_code == 200

        # Force overdue state to validate automatic penalty behavior.
        with SessionLocal() as db:
            opening_row = db.query(HygieneOpening).filter(HygieneOpening.id == opening["opening_id"]).first()
            opening_row.due_back_at = datetime.now(timezone.utc) - timedelta(seconds=120)
            db.add(opening_row)
            db.commit()

        overdue_resp = client.get(f"/api/sessions/{session_id}/hygiene/openings/{opening['opening_id']}")
        assert overdue_resp.status_code == 200
        overdue_data = overdue_resp.json()
        assert overdue_data["status"] == "overdue"
        assert overdue_data["penalty_seconds"] >= 120

        relock_resp = client.post(
            f"/api/sessions/{session_id}/hygiene/openings/{opening['opening_id']}/relock",
            json={"new_seal_number": "A-2"},
        )
        assert relock_resp.status_code == 200
        relocked = relock_resp.json()
        assert relocked["status"] == "closed"
        assert relocked["new_seal_number"] == "A-2"
        assert relocked["penalty_seconds"] >= 120
