from fastapi.testclient import TestClient

from app.main import app


def _create_and_sign_session(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Alpha Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
            "contract_goal": "Alpha smoke test",
            "contract_touch_rules": "Nur nach expliziter Erlaubnis.",
        },
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    sign_resp = client.post(f"/api/sessions/{session_id}/sign-contract")
    assert sign_resp.status_code == 200
    return session_id


def test_alpha_happy_path_smoke_flow():
    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        session_resp = client.get(f"/api/sessions/{session_id}")
        assert session_resp.status_code == 200
        assert session_resp.json()["status"] == "active"
        assert session_resp.json()["contract_signed"] is True

        chat_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Bitte Aufgabe: 30 Kniebeugen in 15 Minuten"},
        )
        assert chat_resp.status_code == 200

        tasks_resp = client.get(f"/api/sessions/{session_id}/tasks")
        assert tasks_resp.status_code == 200
        chat_tasks = tasks_resp.json()["items"]
        assert any("Kniebeugen" in item["title"] for item in chat_tasks)

        verify_task_resp = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={
                "title": "Verifikationsbild senden",
                "description": "Plombe und Zustand klar zeigen",
                "requires_verification": True,
                "verification_criteria": "Plombe muss lesbar sein.",
            },
        )
        assert verify_task_resp.status_code == 200
        verify_task_id = verify_task_resp.json()["task_id"]

        verification_req = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={
                "linked_task_id": verify_task_id,
                "requested_seal_number": "ALPHA-1",
                "verification_criteria": "Plombe muss lesbar sein.",
            },
        )
        assert verification_req.status_code == 200
        verification_id = verification_req.json()["verification_id"]

        upload_resp = client.post(
            f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
            files={"file": ("proof.jpg", b"alpha-proof", "image/jpeg")},
            data={"observed_seal_number": "ALPHA-1"},
        )
        assert upload_resp.status_code == 200
        assert upload_resp.json()["status"] == "confirmed"

        contract_export = client.get(f"/api/sessions/{session_id}/contract/export?format=text")
        assert contract_export.status_code == 200
        assert "vertrag" in contract_export.text.lower()

        events_export = client.get(f"/api/sessions/{session_id}/events/export?format=json")
        assert events_export.status_code == 200
        assert events_export.json()["session_id"] == session_id

        sub_resp = client.post(
            f"/api/sessions/{session_id}/push/subscriptions",
            json={
                "endpoint": "https://example.invalid/push/alpha",
                "keys": {"p256dh": "alpha", "auth": "beta"},
                "user_agent": "pytest-alpha-smoke",
            },
        )
        assert sub_resp.status_code == 200

        push_resp = client.post(f"/api/sessions/{session_id}/push/test", json={})
        assert push_resp.status_code == 200
        assert push_resp.json()["subscriptions"] == 1


def test_alpha_safety_abort_smoke_flow():
    with TestClient(app) as client:
        session_id = _create_and_sign_session(client)

        safeword_resp = client.post(f"/api/sessions/{session_id}/safety/safeword")
        assert safeword_resp.status_code == 200
        assert safeword_resp.json()["status"] == "safeword_stopped"

        session_resp = client.get(f"/api/sessions/{session_id}")
        assert session_resp.status_code == 200
        assert session_resp.json()["status"] == "safeword_stopped"

        logs_resp = client.get(f"/api/sessions/{session_id}/safety/logs")
        assert logs_resp.status_code == 200
        assert any(item["event_type"] == "safeword" for item in logs_resp.json()["logs"])

        chat_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Bist du noch da?"},
        )
        assert chat_resp.status_code == 200
        assert "Safety-Stop" in chat_resp.json()["reply"]
