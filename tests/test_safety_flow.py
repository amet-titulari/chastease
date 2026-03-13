from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _admin_headers() -> dict:
    s = settings.admin_secret
    return {"X-Admin-Secret": s} if s else {}


def _create_and_sign_session(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Safety Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_traffic_light_and_emergency_logging():
    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        yellow = client.post(
            f"/api/sessions/{session_id}/safety/traffic-light",
            json={"color": "yellow"},
            headers=_admin_headers(),
        )
        assert yellow.status_code == 200
        assert yellow.json()["status"] in {"active", "paused"}

        red = client.post(
            f"/api/sessions/{session_id}/safety/traffic-light",
            json={"color": "red"},
            headers=_admin_headers(),
        )
        assert red.status_code == 200
        assert red.json()["status"] == "paused"

        emergency = client.post(
            f"/api/sessions/{session_id}/safety/emergency-release",
            json={"reason": "Physical discomfort detected"},
            headers=_admin_headers(),
        )
        assert emergency.status_code == 200
        assert emergency.json()["status"] == "emergency_stopped"

        logs = client.get(f"/api/sessions/{session_id}/safety/logs")
        assert logs.status_code == 200
        events = [entry["event_type"] for entry in logs.json()["logs"]]
        assert "yellow" in events
        assert "red" in events
        assert "emergency_release" in events


def test_admin_secret_protects_control_actions_when_configured():
    previous = settings.admin_secret
    settings.admin_secret = "safety-secret"
    try:
        with TestClient(app) as client:
            session_id = _create_and_sign_session(client)

            blocked_traffic = client.post(
                f"/api/sessions/{session_id}/safety/traffic-light",
                json={"color": "yellow"},
            )
            assert blocked_traffic.status_code == 403

            blocked_emergency = client.post(
                f"/api/sessions/{session_id}/safety/emergency-release",
                json={"reason": "Physical discomfort detected"},
            )
            assert blocked_emergency.status_code == 403

            allowed_traffic = client.post(
                f"/api/sessions/{session_id}/safety/traffic-light",
                json={"color": "yellow"},
                headers={"X-Admin-Secret": "safety-secret"},
            )
            assert allowed_traffic.status_code == 200

            allowed_emergency = client.post(
                f"/api/sessions/{session_id}/safety/emergency-release",
                json={"reason": "Physical discomfort detected"},
                headers={"X-Admin-Secret": "safety-secret"},
            )
            assert allowed_emergency.status_code == 200

            safeword = client.post(f"/api/sessions/{session_id}/safety/safeword")
            assert safeword.status_code == 200
    finally:
        settings.admin_secret = previous
