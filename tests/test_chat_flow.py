import json

from fastapi.testclient import TestClient
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.message import Message
from app.models.persona import Persona
from app.models.persona_task_template import PersonaTaskTemplate
from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.services.transcription_service import TranscriptionResult


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


def test_chat_surfaces_degraded_ai_mode(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            return AIResponse(
                message="Chat Persona: Der Leitkanal ist gerade instabil.",
                actions=[],
                mood="caring",
                intensity=2,
                degraded=True,
                degraded_reason="provider offline",
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda **_: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Status update"},
        )
        assert send_resp.status_code == 200
        assert "Leitkanal" in send_resp.json()["reply"]

        list_resp = client.get(f"/api/sessions/{session_id}/messages")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert any(item["message_type"] == "system_warning" for item in items)


def test_chat_reply_switches_to_care_mode_on_yellow():
    with TestClient(app) as client:
        _register_user(client, prefix="chat-admin-yellow", make_admin=True)
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
        assert send_resp.json()["client_actions"] == []


def test_chat_reply_respects_pause_on_red():
    with TestClient(app) as client:
        _register_user(client, prefix="chat-admin-red", make_admin=True)
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


def test_chat_persists_prompt_metadata(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            return AIResponse(
                message="Verstanden.",
                actions=[],
                mood="strict",
                intensity=3,
            )

    def _fake_get_ai_gateway(session_obj):
        _ = session_obj
        return _DummyAI()

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", _fake_get_ai_gateway)

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Kurzer Check-in."},
        )
        assert send_resp.status_code == 200


def test_chat_can_update_roleplay_state(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Bleib in der Inspection und melde Haltung.",
                actions=[
                    {
                        "type": "update_roleplay_state",
                        "scene": {
                            "title": "Inspection",
                            "objective": "Haltung, Gehorsam und Praesenz pruefen",
                            "last_consequence": "Ton wurde verschaerft",
                            "next_beat": "Statusmeldung in Pose",
                        },
                        "relationship": {
                            "obedience": 77,
                            "strictness": 74,
                            "control_level": "inspection",
                        },
                        "protocol": {
                            "active_rules": ["Haende hinter den Kopf", "Beine gespreizt stehen"],
                            "open_orders": ["Pose halten und still melden"],
                        },
                    }
                ],
                mood="strict",
                intensity=4,
            )

    def _fake_get_ai_gateway(session_obj):
        _ = session_obj
        return _DummyAI()

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", _fake_get_ai_gateway)

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Ich bin bereit."},
        )
        assert send_resp.status_code == 200

        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        state = detail_resp.json()["roleplay_state"]
        assert state["scene"]["title"] == "Inspection"
        assert state["relationship"]["obedience"] == 77
        assert state["relationship"]["control_level"] == "inspection"
        assert state["protocol"]["open_orders"] == ["Pose halten und still melden"]

        db = SessionLocal()
        try:
            update_msg = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.message_type == "session_state_updated")
                .order_by(Message.id.desc())
                .first()
            )
            assert update_msg is not None
            assert "Inspection" in update_msg.content
        finally:
            db.close()


def test_chat_returns_lovense_client_actions(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Kurzer Impuls fuer den Edge 2.",
                actions=[
                    {
                        "type": "lovense_control",
                        "command": "pulse",
                        "intensity": 9,
                        "duration_seconds": 15,
                        "pause_seconds": 3,
                        "loops": 2,
                    }
                ],
                mood="strict",
                intensity=4,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Uebernimm die Toy-Steuerung."},
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["client_actions"] == [
            {
                "type": "lovense_control",
                "command": "pulse",
                "intensity": 9,
                "duration_seconds": 15,
                "pause_seconds": 3,
                "loops": 2,
            }
        ]


def test_chat_returns_lovense_session_plan(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Ich starte jetzt eine gefuehrte Sequenz.",
                actions=[
                    {
                        "type": "lovense_session_plan",
                        "title": "Warmup Block",
                        "steps": [
                            {"command": "pulse", "intensity": 7, "duration_seconds": 12},
                            {"command": "pause", "duration_seconds": 5},
                            {"command": "preset", "preset": "tease_ramp", "duration_seconds": 18},
                        ],
                    }
                ],
                mood="strict",
                intensity=4,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Starte eine laengere Edge-2-Session."},
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["client_actions"] == [
            {
                "type": "lovense_session_plan",
                "title": "Warmup Block",
                "mode": "replace",
                "steps": [
                    {"command": "pulse", "intensity": 7, "duration_seconds": 12},
                    {"command": "pause", "duration_seconds": 5},
                    {"command": "preset", "preset": "tease_ramp", "duration_seconds": 18},
                ],
            }
        ]


def test_chat_filters_stimulating_lovense_actions_when_session_is_paused(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Ich stoppe und beruhige die Lage.",
                actions=[
                    {"type": "lovense_control", "command": "pulse", "intensity": 10, "duration_seconds": 12},
                    {"type": "lovense_control", "command": "stop"},
                ],
                mood="caring",
                intensity=2,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        _register_user(client, prefix="chat-admin-pause", make_admin=True)
        session_id = _create_and_sign(client)

        red = client.post(
            f"/api/sessions/{session_id}/safety/traffic-light",
            json={"color": "red"},
            headers=_admin_headers(),
        )
        assert red.status_code == 200

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Was jetzt?"},
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["client_actions"] == [{"type": "lovense_control", "command": "stop"}]


def test_chat_filters_stimulating_lovense_session_plans_when_session_is_paused(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Ich breche die Sequenz ab.",
                actions=[
                    {
                        "type": "lovense_session_plan",
                        "title": "Unsafe Block",
                        "steps": [
                            {"command": "pulse", "intensity": 9, "duration_seconds": 10},
                            {"command": "stop"},
                        ],
                    }
                ],
                mood="caring",
                intensity=2,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        _register_user(client, prefix="chat-admin-planpause", make_admin=True)
        session_id = _create_and_sign(client)

        red = client.post(
            f"/api/sessions/{session_id}/safety/traffic-light",
            json={"color": "red"},
            headers=_admin_headers(),
        )
        assert red.status_code == 200

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Beruhige alles sofort."},
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["client_actions"] == [
            {
                "type": "lovense_session_plan",
                "title": "Unsafe Block",
                "mode": "replace",
                "steps": [{"command": "stop"}],
            }
        ]


def test_chat_clamps_lovense_actions_to_saved_policy(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="Clamp test",
                actions=[
                    {
                        "type": "lovense_control",
                        "command": "pulse",
                        "intensity": 20,
                        "duration_seconds": 80,
                        "pause_seconds": 0,
                        "loops": 2,
                    },
                    {
                        "type": "lovense_session_plan",
                        "title": "Clamp me",
                        "mode": "append",
                        "steps": [
                            {"command": "wave", "intensity": 18, "duration_seconds": 40},
                            {"command": "pause", "duration_seconds": 1},
                            {"command": "preset", "preset": "tease_ramp", "duration_seconds": 30},
                        ],
                    },
                ],
                mood="strict",
                intensity=4,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)
        with SessionLocal() as db:
            session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
            prefs = json.loads(profile.preferences_json or "{}")
            prefs["toys"] = {
                "lovense_policy": {
                    "min_intensity": 4,
                    "max_intensity": 12,
                    "min_step_duration_seconds": 5,
                    "max_step_duration_seconds": 25,
                    "min_pause_seconds": 3,
                    "max_pause_seconds": 10,
                    "max_plan_duration_seconds": 20,
                    "max_plan_steps": 2,
                    "allow_presets": False,
                    "allow_append_mode": False,
                    "allowed_commands": {
                        "vibrate": True,
                        "pulse": True,
                        "wave": True,
                        "preset": False,
                    },
                }
            }
            profile.preferences_json = json.dumps(prefs)
            db.add(profile)
            db.commit()

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Clamp please"},
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["client_actions"] == [
            {
                "type": "lovense_control",
                "command": "pulse",
                "intensity": 12,
                "duration_seconds": 25,
                "pause_seconds": 3,
                "loops": 2,
            },
            {
                "type": "lovense_session_plan",
                "title": "Clamp me",
                "mode": "replace",
                "steps": [
                    {"command": "wave", "intensity": 12, "duration_seconds": 20},
                ],
            },
        ]


def test_chat_infers_roleplay_update_from_reply_text(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message=(
                    "Belohnung fliesst: trust=67 (+5), obedience=60 (+5). "
                    "Wir bleiben fokussiert."
                ),
                actions=[],
                mood="strict",
                intensity=4,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Kannst du meine Werte aktualisieren?"},
        )
        assert send_resp.status_code == 200

        detail_resp = client.get(f"/api/sessions/{session_id}")
        assert detail_resp.status_code == 200
        state = detail_resp.json()["roleplay_state"]
        assert state["relationship"]["trust"] == 67
        assert state["relationship"]["obedience"] == 60


def test_chat_handles_pending_tasks_without_deadline(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse
            _ = kwargs
            return AIResponse(
                message="Verstanden.",
                actions=[],
                mood="strict",
                intensity=3,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        db = SessionLocal()
        try:
            task = Task(
                session_id=session_id,
                title="Task ohne Deadline",
                description="Regression test",
                status="pending",
                deadline_at=None,
            )
            db.add(task)
            db.commit()
        finally:
            db.close()

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Kurzer Status"},
        )
        assert send_resp.status_code == 200


def test_chat_injects_roleplay_memory_into_ai_context(monkeypatch):
    captured = {}

    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            captured["context_items"] = kwargs.get("context_items") or []
            return AIResponse(
                message="Verstanden.",
                actions=[],
                mood="strict",
                intensity=3,
            )

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", lambda session_obj: _DummyAI())

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Kurzer Lagebericht."},
        )
        assert send_resp.status_code == 200
        assert any(item.get("message_type") == "roleplay_memory" for item in captured.get("context_items", []))


def test_chat_falls_back_to_persona_task_template_when_ai_returns_no_task(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message="In Ordnung.",
                actions=[],
                mood="strict",
                intensity=3,
            )

    def _fake_get_ai_gateway(session_obj):
        _ = session_obj
        return _DummyAI()

    db = SessionLocal()
    try:
        persona = Persona(name="Pool Persona", description="Template pool test")
        db.add(persona)
        db.flush()
        db.add(
            PersonaTaskTemplate(
                persona_id=persona.id,
                title="Abendlicher Foto-Check-in",
                description="Schicke einen kurzen Status mit aktuellem Foto.",
                deadline_minutes=180,
                requires_verification=True,
                verification_criteria="Plombe und Uhrzeit sichtbar",
                category="checkin",
                tags_json='["abend", "foto", "checkin"]',
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", _fake_get_ai_gateway)

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Pool Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
            },
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
        assert sign_resp.status_code == 200

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Bitte gib mir eine Aufgabe fuer heute Abend mit Foto."},
        )
        assert send_resp.status_code == 200

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.session_id == session_id).order_by(Task.id.desc()).first()
            assert task is not None
            assert task.title == "Abendlicher Foto-Check-in"
            assert task.requires_verification is True
            assert task.verification_criteria == "Plombe und Uhrzeit sichtbar"
        finally:
            db.close()


def test_chat_infers_task_from_assistant_assignment_when_action_is_missing(monkeypatch):
    class _DummyAI:
        def generate_chat_response(self, **kwargs):
            from app.services.ai_gateway import AIResponse

            _ = kwargs
            return AIResponse(
                message=(
                    "Ich fuehre dich weiter. Aktuelle Pflicht: Halte heute bis spaetestens 20:00 die "
                    "Abendkontrolle ein. Verifizierung mit Uhrzeit und Plombe gut sichtbar."
                ),
                actions=[],
                mood="strict",
                intensity=4,
            )

    def _fake_get_ai_gateway(session_obj):
        _ = session_obj
        return _DummyAI()

    monkeypatch.setattr("app.routers.chat.get_ai_gateway", _fake_get_ai_gateway)

    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        send_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Hallo Herrin."},
        )
        assert send_resp.status_code == 200

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.session_id == session_id).order_by(Task.id.desc()).first()
            assert task is not None
            assert "Abendkontrolle" in task.title
            assert task.requires_verification is True
            assert task.verification_criteria is not None

            task_msg = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.message_type == "task_assigned")
                .order_by(Message.id.desc())
                .first()
            )
            assert task_msg is not None
            assert "Abendkontrolle" in task_msg.content
        finally:
            db.close()
        payload = send_resp.json()
        assert payload["prompt_version"] is not None
        assert "base_system_prompt.jinja2" in payload["prompt_templates"]

        db = SessionLocal()
        try:
            assistant_msg = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.role == "assistant")
                .order_by(Message.id.desc())
                .first()
            )
            assert assistant_msg is not None
            assert assistant_msg.prompt_version is not None
            assert assistant_msg.prompt_templates_json is not None

            list_resp = client.get(f"/api/sessions/{session_id}/messages")
            assert list_resp.status_code == 200
            items = list_resp.json()["items"]
            assistant_rows = [item for item in items if item["role"] == "assistant"]
            assert assistant_rows
            assert assistant_rows[-1]["prompt_version"] == assistant_msg.prompt_version
            assert "base_system_prompt.jinja2" in assistant_rows[-1]["prompt_templates"]
        finally:
            db.close()
