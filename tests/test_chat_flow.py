from fastapi.testclient import TestClient

from app.main import app


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Chat Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_chat_message_roundtrip():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Status update"},
        )
        assert send_resp.status_code == 200
        assert "reply" in send_resp.json()

        list_resp = client.get(f"/api/sessions/{session_id}/messages")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) >= 2
        assert items[-2]["role"] == "user"
        assert items[-1]["role"] == "assistant"


def test_chat_reply_switches_to_care_mode_on_yellow():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        yellow = client.post(
            f"/api/sessions/{session_id}/safety/traffic-light",
            json={"color": "yellow"},
        )
        assert yellow.status_code == 200

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Ich brauche kurz weniger Druck."},
        )
        assert send_resp.status_code == 200
        assert "Fuersorge-Modus" in send_resp.json()["reply"]


def test_chat_reply_respects_pause_on_red():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        red = client.post(
            f"/api/sessions/{session_id}/safety/traffic-light",
            json={"color": "red"},
        )
        assert red.status_code == 200
        assert red.json()["status"] == "paused"

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Status?"},
        )
        assert send_resp.status_code == 200
        assert "Session bleibt pausiert" in send_resp.json()["reply"]
