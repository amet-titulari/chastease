from datetime import timedelta

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.session import Session
from app.models.task import Task


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Psych Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_profile_multiplier_affects_failed_task_penalty():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        profile_update = client.put(
            f"/api/sessions/{session_id}/player-profile",
            json={
                "experience_level": "advanced",
                "reaction_patterns": {"penalty_multiplier": 2.0, "max_penalty_seconds": 2000},
            },
        )
        assert profile_update.status_code == 200

        with SessionLocal() as db:
            before = db.query(Session).filter(Session.id == session_id).first()
            lock_end_before = before.lock_end

        create_task = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={"title": "Penalty profile test"},
        )
        task_id = create_task.json()["task_id"]

        fail = client.post(
            f"/api/sessions/{session_id}/tasks/{task_id}/status",
            json={"status": "failed"},
        )
        assert fail.status_code == 200

        with SessionLocal() as db:
            task_row = db.query(Task).filter(Task.id == task_id).first()
            after = db.query(Session).filter(Session.id == session_id).first()
            assert task_row.consequence_applied_seconds == 720
            assert after.lock_end == lock_end_before + timedelta(seconds=720)


def test_hard_limits_block_ai_created_tasks_from_chat():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        profile_update = client.put(
            f"/api/sessions/{session_id}/player-profile",
            json={"hard_limits": ["kniebeugen"]},
        )
        assert profile_update.status_code == 200

        chat_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Bitte Aufgabe: 30 Kniebeugen in 15 Minuten"},
        )
        assert chat_resp.status_code == 200

        list_tasks = client.get(f"/api/sessions/{session_id}/tasks")
        assert list_tasks.status_code == 200
        titles = [item["title"].lower() for item in list_tasks.json()["items"]]
        assert not any("kniebeugen" in title for title in titles)
