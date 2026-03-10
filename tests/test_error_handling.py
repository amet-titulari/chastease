from fastapi.testclient import TestClient

from app.main import app


def test_http_error_payload_shape():
    with TestClient(app) as client:
        resp = client.get("/api/sessions/999999")
        assert resp.status_code == 404
        data = resp.json()
        assert "request_id" in data
        assert data["error"]["code"] == "http_error"
        assert "message" in data["error"]
        assert data["detail"] == data["error"]["message"]


def test_validation_error_payload_shape():
    with TestClient(app) as client:
        resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "P",
                "player_nickname": "W",
                # missing min_duration_seconds
                "max_duration_seconds": 900,
            },
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "validation_error"
        assert data["error"]["message"] == "Request validation failed"
        assert isinstance(data["error"].get("details"), list)
