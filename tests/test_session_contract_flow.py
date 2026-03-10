from fastapi.testclient import TestClient

from app.main import app


def test_session_starts_only_after_contract_signature():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Test Persona",
                "player_nickname": "Tester",
                "min_duration_seconds": 300,
                "max_duration_seconds": 600,
            },
        )
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert data["status"] == "draft"
        assert data["contract_required"] is True
        assert "KEUSCHHEITS-VERTRAG" in data["contract_preview"]
        assert "Test Persona" in data["contract_preview"]

        sign_resp = client.post(f"/api/sessions/{data['session_id']}/sign-contract")
        assert sign_resp.status_code == 200
        signed = sign_resp.json()
        assert signed["status"] == "active"


def test_contract_addendum_consent_flow():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        propose_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda",
            json={
                "change_description": "Reduce minimum duration",
                "proposed_changes": {"min_duration_seconds": 240},
            },
        )
        assert propose_resp.status_code == 200
        addendum_id = propose_resp.json()["addendum_id"]

        consent_resp = client.post(
            f"/api/sessions/{session_id}/contract/addenda/{addendum_id}/consent",
            json={"decision": "approved"},
        )
        assert consent_resp.status_code == 200
        assert consent_resp.json()["decision"] == "approved"
