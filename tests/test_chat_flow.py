from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.message import Message
from app.models.task import Task
from app.services.transcription_service import TranscriptionResult


def _admin_headers() -> dict:
    s = settings.admin_secret
    return {"X-Admin-Secret": s} if s else {}


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
            headers=_admin_headers(),
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
            headers=_admin_headers(),
        )
        assert red.status_code == 200
        assert red.json()["status"] == "paused"

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Status?"},
        )
        assert send_resp.status_code == 200
        assert "Session bleibt pausiert" in send_resp.json()["reply"]


def test_chat_can_regenerate_last_response():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        first = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Status update"},
        )
        assert first.status_code == 200

        regen = client.post(
            f"/api/sessions/{session_id}/messages/regenerate",
            json={},
        )
        assert regen.status_code == 200
        body = regen.json()
        assert body["message_type"] == "chat_regenerated"
        assert "reply" in body


def test_chat_media_message_with_image():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        resp = client.post(
            f"/api/sessions/{session_id}/messages/media",
            data={"content": "Siehe Bild"},
            files={"file": ("test.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["message_type"] == "chat_image"
        assert "reply" in payload


def test_chat_media_message_with_audio():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        original = settings.transcription_enabled
        settings.transcription_enabled = False
        try:
            resp = client.post(
                f"/api/sessions/{session_id}/messages/media",
                data={"content": "Kurzes Update"},
                files={"file": ("clip.mp3", b"ID3\x03\x00\x00\x00\x00\x00\x21", "audio/mpeg")},
            )
        finally:
            settings.transcription_enabled = original

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["message_type"] == "chat_audio"
        assert payload["transcription_status"] == "disabled"
        assert payload["transcript"] is None
        assert "reply" in payload


def test_chat_media_message_with_audio_transcription(monkeypatch):
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        def _fake_transcribe_audio(**_: object) -> TranscriptionResult:
            return TranscriptionResult(status="ok", text="Das ist ein Testtranskript.", provider="mock", model="mock")

        monkeypatch.setattr("app.routers.chat.transcribe_audio", _fake_transcribe_audio)

        resp = client.post(
            f"/api/sessions/{session_id}/messages/media",
            data={"content": "Bitte auswerten"},
            files={"file": ("clip.webm", b"RIFF....", "audio/webm")},
        )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["message_type"] == "chat_audio"
        assert payload["transcription_status"] == "ok"
        assert payload["transcript"] == "Das ist ein Testtranskript."


def test_chat_update_task_action_updates_deadline(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            return AIResponse(
                message="Deadline wurde angepasst.",
                actions=[{"type": "update_task", "task_id": 0, "deadline_minutes": 270}],
                mood="strict",
                intensity=3,
            )

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        create_task_resp = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={
                "title": "Task fuer Deadline-Update",
                "description": "Test",
                "deadline_minutes": 30,
            },
        )
        assert create_task_resp.status_code == 200
        task_id = create_task_resp.json()["task_id"]

        def _fake_get_ai_gateway(session_obj):
            _ = session_obj
            ai = _DummyAI()
            ai_response = ai.generate_chat_response

            def _wrapped_generate_chat_response(**kwargs):
                result = ai_response(**kwargs)
                result.actions[0]["task_id"] = task_id
                return result

            ai.generate_chat_response = _wrapped_generate_chat_response
            return ai

        monkeypatch.setattr("app.routers.chat.get_ai_gateway", _fake_get_ai_gateway)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Setze bitte die Deadline auf 09:00."},
        )
        assert send_resp.status_code == 200

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            assert task is not None
            assert task.deadline_at is not None

            task_updated_msg = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.message_type == "task_updated")
                .order_by(Message.id.desc())
                .first()
            )
            assert task_updated_msg is not None
            assert f"#{task_id}" in task_updated_msg.content
            assert "deadline(+270m)" in task_updated_msg.content
        finally:
            db.close()
