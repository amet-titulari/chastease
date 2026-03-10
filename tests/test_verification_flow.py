from fastapi.testclient import TestClient

from app.main import app


def _create_and_sign_session(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Verification Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_verification_upload_and_seal_mismatch_marks_suspicious():
    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        request_resp = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={"requested_seal_number": "A-2"},
        )
        assert request_resp.status_code == 200
        verification_id = request_resp.json()["verification_id"]

        upload_resp = client.post(
            f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
            files={"file": ("proof.jpg", b"fake-image-bytes", "image/jpeg")},
            data={"observed_seal_number": "A-9"},
        )
        assert upload_resp.status_code == 200
        data = upload_resp.json()
        assert data["status"] == "suspicious"
        assert "stimmt nicht" in data["analysis"]
