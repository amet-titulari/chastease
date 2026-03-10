from fastapi.testclient import TestClient

from app.main import app


def _create_and_sign(client: TestClient) -> tuple[int, str]:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Timer WS Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id, sign_resp.json()["ws_auth_token"]


def test_websocket_streams_timer_tick_when_enabled():
    with TestClient(app) as client:
        session_id, token = _create_and_sign(client)

        with client.websocket_connect(
            f"/api/sessions/{session_id}/chat/ws?token={token}&stream_timer=1"
        ) as ws:
            payload = ws.receive_json()
            assert payload["message_type"] == "timer_tick"
            assert isinstance(payload["remaining_seconds"], int)
            assert payload["remaining_seconds"] >= 0
