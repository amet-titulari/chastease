from fastapi.testclient import TestClient

from app.main import app


def test_session_detail_and_seal_history_endpoints():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Obs Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        client.post(
            f"/api/sessions/{session_id}/hygiene/openings",
            json={"duration_seconds": 120, "old_seal_number": "S-1"},
        )

        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "active"
        assert detail["contract_signed"] is True

        history_resp = client.get(f"/api/sessions/{session_id}/seal-history")
        assert history_resp.status_code == 200
        entries = history_resp.json()["entries"]
        assert len(entries) >= 1
        assert entries[0]["seal_number"] == "S-1"


def test_verification_list_endpoint():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Verif Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        req_resp = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={"requested_seal_number": "X-1"},
        )
        verification_id = req_resp.json()["verification_id"]

        client.post(
            f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
            files={"file": ("proof.jpg", b"bytes", "image/jpeg")},
            data={"observed_seal_number": "X-1"},
        )

        list_resp = client.get(f"/api/sessions/{session_id}/verifications")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["status"] in {"confirmed", "suspicious"}
