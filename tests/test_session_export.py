from fastapi.testclient import TestClient

from app.main import app


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Export Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_session_export_text_json_pdf():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)
        client.post(f"/api/sessions/{session_id}/messages", json={"content": "Export test"})

        text_resp = client.get(f"/api/sessions/{session_id}/export?format=text")
        assert text_resp.status_code == 200
        assert "EVENTS:" in text_resp.text
        assert f"session_id={session_id}" in text_resp.text

        json_resp = client.get(f"/api/sessions/{session_id}/export?format=json")
        assert json_resp.status_code == 200
        payload = json_resp.json()
        assert payload["session_id"] == session_id
        assert isinstance(payload["items"], list)

        pdf_resp = client.get(f"/api/sessions/{session_id}/export?format=pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"].startswith("application/pdf")
        assert pdf_resp.content.startswith(b"%PDF-")
