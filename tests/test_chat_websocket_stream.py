from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.message import Message


def _create_and_sign(client: TestClient) -> tuple[int, str]:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "WS Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
    ws_auth_token = sign_resp.json()["ws_auth_token"]
    return session_id, ws_auth_token


def test_websocket_streams_proactive_messages():
    with TestClient(app) as client:
        session_id, ws_auth_token = _create_and_sign(client)

        with client.websocket_connect(f"/api/sessions/{session_id}/chat/ws?token={ws_auth_token}") as ws:
            with SessionLocal() as db:
                db.add(
                    Message(
                        session_id=session_id,
                        role="assistant",
                        content="Proaktiver Hinweis",
                        message_type="proactive_reminder",
                    )
                )
                db.commit()

            payload = ws.receive_json()
            assert payload["message_type"] == "proactive_reminder"
            assert "Proaktiver Hinweis" in payload["assistant"]


def test_websocket_rejects_missing_token():
    with TestClient(app) as client:
        session_id, _ = _create_and_sign(client)
        with client.websocket_connect(f"/api/sessions/{session_id}/chat/ws") as ws:
            data = ws.receive()
            assert data["type"] == "websocket.close"
