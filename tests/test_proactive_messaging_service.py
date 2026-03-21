from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.message import Message
from app.services.proactive_messaging import sweep_proactive_messages_for_active_sessions


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Reminder Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_proactive_sweep_creates_assistant_reminder():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        result = sweep_proactive_messages_for_active_sessions()
        assert result["scanned_sessions"] >= 1
        assert result["sent_messages"] >= 1

        with SessionLocal() as db:
            rows = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.message_type == "proactive_reminder")
                .all()
            )
            assert len(rows) == 1
            assert rows[0].role == "assistant"


def test_proactive_sweep_uses_scene_context():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        with SessionLocal() as db:
            from app.models.session import Session as SessionModel

            row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            row.scene_state_json = '{"title": "Inspection", "objective": "Praesente Haltung halten", "next_beat": "Kurzen Status liefern"}'
            row.protocol_state_json = '{"active_rules": ["Ohne Ausfluechte antworten"]}'
            db.add(row)
            db.commit()

        sweep_proactive_messages_for_active_sessions()

        with SessionLocal() as db:
            reminder = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.message_type == "proactive_reminder")
                .order_by(Message.id.desc())
                .first()
            )
            assert reminder is not None
            assert "Inspection" in reminder.content
            assert "Ohne Ausfluechte antworten" in reminder.content


def test_proactive_sweep_can_use_ai_prompt_path(monkeypatch):
    captured = {}

    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            captured["user_text"] = kwargs.get("user_text")
            captured["prompt_modules"] = kwargs.get("prompt_modules")
            captured["context_items"] = kwargs.get("context_items") or []
            return AIResponse(
                message="Reminder Persona: Bleib praesent und liefere einen knappen Status.",
                actions=[],
                mood="strict",
                intensity=3,
            )

    monkeypatch.setattr("app.services.proactive_messaging.get_ai_gateway", lambda session_obj=None: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        result = sweep_proactive_messages_for_active_sessions()
        assert result["sent_messages"] >= 1
        assert "proaktive Reminder-Nachricht" in str(captured.get("user_text") or "")
        assert "Roleplay-Status" not in str(captured.get("prompt_modules") or "")
        assert any(item.get("message_type") == "reminder_context" for item in captured.get("context_items", []))


def test_proactive_sweep_respects_cooldown():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        first = sweep_proactive_messages_for_active_sessions()
        assert first["sent_messages"] >= 1

        second = sweep_proactive_messages_for_active_sessions()
        assert second["sent_messages"] == 0

        with SessionLocal() as db:
            rows = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.message_type == "proactive_reminder")
                .all()
            )
            assert len(rows) == 1
