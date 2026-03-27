from fastapi.testclient import TestClient
from uuid import uuid4

from app.database import SessionLocal
from app.config import settings
from app.main import app
from app.models.message import Message


def _admin_headers() -> dict:
    s = settings.admin_secret
    return {"X-Admin-Secret": s} if s else {}


def _register_user(client: TestClient, prefix: str, make_admin: bool) -> None:
    unique = uuid4().hex[:8]
    email = f"{prefix}-{unique}@example.com"

    if make_admin:
        existing = settings.admin_bootstrap_emails or ""
        settings.admin_bootstrap_emails = ",".join([item for item in [existing, email] if item])

    resp = client.post(
        "/auth/register",
        data={
            "username": f"{prefix}-{unique}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


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
        _register_user(client, prefix="ws-admin-stream", make_admin=True)
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
        _register_user(client, prefix="ws-admin-missing", make_admin=True)
        session_id, _ = _create_and_sign(client)
        with client.websocket_connect(f"/api/sessions/{session_id}/chat/ws") as ws:
            data = ws.receive()
            assert data["type"] == "websocket.close"


def test_rotate_ws_token_returns_new_token():
    with TestClient(app) as client:
        _register_user(client, prefix="ws-admin-rotate", make_admin=True)
        session_id, ws_auth_token = _create_and_sign(client)

        rotate_resp = client.post(
            f"/api/sessions/{session_id}/chat/ws-token/rotate",
            headers=_admin_headers(),
        )
        assert rotate_resp.status_code == 200
        rotated = rotate_resp.json()
        assert rotated["session_id"] == session_id
        assert rotated["ws_auth_token"]
        assert rotated["ws_auth_token"] != ws_auth_token


def test_rotate_ws_token_invalidates_existing_connection():
    with TestClient(app) as client:
        _register_user(client, prefix="ws-admin-invalidates", make_admin=True)
        session_id, ws_auth_token = _create_and_sign(client)

        with client.websocket_connect(f"/api/sessions/{session_id}/chat/ws?token={ws_auth_token}") as ws:
            rotate_resp = client.post(
                f"/api/sessions/{session_id}/chat/ws-token/rotate",
                headers=_admin_headers(),
            )
            assert rotate_resp.status_code == 200

            # Next interaction should be rejected because token was rotated server-side.
            ws.send_text("Hallo")
            closed = ws.receive()
            assert closed["type"] == "websocket.close"

        new_token = rotate_resp.json()["ws_auth_token"]
        with client.websocket_connect(f"/api/sessions/{session_id}/chat/ws?token={new_token}") as ws_new:
            ws_new.send_text("Neuer Token")
            payload = ws_new.receive_json()
            assert payload["message_type"] == "chat"


def test_websocket_includes_lovense_client_actions(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Kurzer Pulse-Befehl.",
                actions=[{"type": "lovense_control", "command": "pulse", "intensity": 8, "duration_seconds": 10}],
                mood="strict",
                intensity=3,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        _register_user(client, prefix="ws-admin-lovense", make_admin=True)
        session_id, ws_auth_token = _create_and_sign(client)

        with client.websocket_connect(f"/api/sessions/{session_id}/chat/ws?token={ws_auth_token}") as ws:
            ws.send_text("Steuere den Edge 2.")
            payload = ws.receive_json()
            assert payload["message_type"] == "chat"
            assert payload["client_actions"] == [
                {"type": "lovense_control", "command": "pulse", "intensity": 8, "duration_seconds": 10}
            ]


def test_websocket_includes_lovense_session_plan(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Ich uebergebe einen kleinen Session-Plan.",
                actions=[
                    {
                        "type": "lovense_session_plan",
                        "title": "WS Plan",
                        "steps": [
                            {"command": "pulse", "intensity": 6, "duration_seconds": 10},
                            {"command": "pause", "duration_seconds": 4},
                            {"command": "wave", "intensity": 8, "duration_seconds": 9},
                        ],
                    }
                ],
                mood="strict",
                intensity=4,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        _register_user(client, prefix="ws-admin-plan", make_admin=True)
        session_id, ws_auth_token = _create_and_sign(client)

        with client.websocket_connect(f"/api/sessions/{session_id}/chat/ws?token={ws_auth_token}") as ws:
            ws.send_text("Plane jetzt mehrere Schritte.")
            payload = ws.receive_json()
            assert payload["message_type"] == "chat"
            assert payload["client_actions"] == [
                {
                    "type": "lovense_session_plan",
                    "title": "WS Plan",
                    "mode": "replace",
                    "steps": [
                        {"command": "pulse", "intensity": 6, "duration_seconds": 10},
                        {"command": "pause", "duration_seconds": 4},
                        {"command": "wave", "intensity": 8, "duration_seconds": 9},
                    ],
                }
            ]


def test_rotate_ws_token_requires_admin_secret_when_configured():
    previous = settings.admin_secret
    settings.admin_secret = "top-secret"
    try:
        with TestClient(app) as client:
            _register_user(client, prefix="ws-admin-secret", make_admin=True)
            session_id, _ = _create_and_sign(client)

            no_secret = client.post(f"/api/sessions/{session_id}/chat/ws-token/rotate")
            assert no_secret.status_code == 403

            wrong_secret = client.post(
                f"/api/sessions/{session_id}/chat/ws-token/rotate",
                headers={"X-Admin-Secret": "wrong"},
            )
            assert wrong_secret.status_code == 403

            ok_secret = client.post(
                f"/api/sessions/{session_id}/chat/ws-token/rotate",
                headers={"X-Admin-Secret": "top-secret"},
            )
            assert ok_secret.status_code == 200
    finally:
        settings.admin_secret = previous


def test_rotate_ws_token_requires_admin_session():
    with TestClient(app) as client:
        _register_user(client, prefix="ws-user", make_admin=False)
        session_id, _ = _create_and_sign(client)

        rotate_resp = client.post(
            f"/api/sessions/{session_id}/chat/ws-token/rotate",
            headers=_admin_headers(),
        )
        assert rotate_resp.status_code == 403
