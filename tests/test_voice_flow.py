from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Voice Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_voice_realtime_status_reflects_feature_flag(monkeypatch):
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        original = settings.voice_realtime_enabled
        settings.voice_realtime_enabled = True
        try:
            monkeypatch.setattr("app.routers.voice._resolve_xai_key", lambda **_: "test-key")
            resp = client.get(f"/api/voice/realtime/{session_id}/status")
        finally:
            settings.voice_realtime_enabled = original

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["enabled"] is True
        assert payload["has_api_key"] is True
        assert payload["mode"] in {"realtime-manual", "voice-agent"}


def test_voice_realtime_client_secret_bootstrap(monkeypatch):
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        class _FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"client_secret": {"value": "ephemeral-test-token"}}

        class _FakeClient:
            def __init__(self, timeout: float):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, url: str, headers: dict, json: dict):
                assert "Authorization" in headers
                assert json["expires_after"]["seconds"] >= 30
                return _FakeResponse()

        original_enabled = settings.voice_realtime_enabled
        original_mode = settings.voice_realtime_mode
        settings.voice_realtime_enabled = True
        settings.voice_realtime_mode = "realtime-manual"
        try:
            monkeypatch.setattr("app.routers.voice._resolve_xai_key", lambda **_: "test-key")
            monkeypatch.setattr("app.routers.voice.httpx.Client", _FakeClient)

            resp = client.post(f"/api/voice/realtime/{session_id}/client-secret")
        finally:
            settings.voice_realtime_enabled = original_enabled
            settings.voice_realtime_mode = original_mode

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["session_id"] == session_id
        assert payload["client_secret"]["client_secret"]["value"] == "ephemeral-test-token"
        assert payload["session_update"]["type"] == "session.update"
