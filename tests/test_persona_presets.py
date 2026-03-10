from fastapi.testclient import TestClient

from app.main import app


def test_persona_presets_include_ballet_sub_ella():
    with TestClient(app) as client:
        resp = client.get("/api/personas/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert any(item["name"] == "Ballet Sub Ella" for item in data["items"])
        ella = next(item for item in data["items"] if item["key"] == "ballet_sub_ella")
        assert ella["strictness_level"] >= 1
