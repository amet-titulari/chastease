from datetime import datetime

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


def test_session_sign_uses_duration_within_min_max(monkeypatch):
    monkeypatch.setattr("app.services.session_service.random.randint", lambda low, high: 451)

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
        session_id = create_resp.json()["session_id"]

        sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert sign_resp.status_code == 200
        signed = sign_resp.json()
        lock_end = datetime.fromisoformat(signed["lock_end"])

        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        lock_start = datetime.fromisoformat(detail["lock_start"])

        assert int((lock_end - lock_start).total_seconds()) == 451


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


def test_contract_view_and_export_endpoints():
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
        addendum_id = propose_resp.json()["addendum_id"]
        client.post(
            f"/api/sessions/{session_id}/contract/addenda/{addendum_id}/consent",
            json={"decision": "approved"},
        )

        view_resp = client.get(f"/api/sessions/{session_id}/contract")
        assert view_resp.status_code == 200
        payload = view_resp.json()
        assert payload["session_id"] == session_id
        assert "KEUSCHHEITS-VERTRAG" in payload["contract"]["content_text"]
        assert len(payload["addenda"]) >= 1

        export_text = client.get(f"/api/sessions/{session_id}/contract/export?format=text")
        assert export_text.status_code == 200
        assert "ADDENDA" in export_text.text

        export_json = client.get(f"/api/sessions/{session_id}/contract/export?format=json")
        assert export_json.status_code == 200
        assert export_json.json()["session_id"] == session_id
