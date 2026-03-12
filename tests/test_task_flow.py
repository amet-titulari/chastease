from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.models.session import Session
from app.models.task import Task
from app.main import app


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Task Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_task_create_list_and_complete():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        create_task = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={"title": "Routine", "description": "Test", "deadline_minutes": 10},
        )
        assert create_task.status_code == 200
        task_id = create_task.json()["task_id"]

        list_resp = client.get(f"/api/sessions/{session_id}/tasks")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["items"]) >= 1

        complete = client.post(
            f"/api/sessions/{session_id}/tasks/{task_id}/status",
            json={"status": "completed"},
        )
        assert complete.status_code == 200
        assert complete.json()["status"] == "completed"


def test_failed_task_applies_lock_extension_once():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        with SessionLocal() as db:
            session_before = db.query(Session).filter(Session.id == session_id).first()
            lock_end_before = session_before.lock_end

        create_task = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={
                "title": "Failure Case",
                "description": "Should extend lock",
                "consequence_type": "lock_extension_seconds",
                "consequence_value": 180,
            },
        )
        task_id = create_task.json()["task_id"]

        failed = client.post(
            f"/api/sessions/{session_id}/tasks/{task_id}/status",
            json={"status": "failed"},
        )
        assert failed.status_code == 200
        assert failed.json()["status"] == "failed"

        # A second failed update must not stack another penalty.
        failed_again = client.post(
            f"/api/sessions/{session_id}/tasks/{task_id}/status",
            json={"status": "failed"},
        )
        assert failed_again.status_code == 200

        with SessionLocal() as db:
            session_after = db.query(Session).filter(Session.id == session_id).first()
            task_row = db.query(Task).filter(Task.id == task_id).first()
            assert task_row.consequence_applied_seconds == 180
            assert task_row.consequence_applied_at is not None
            assert session_after.lock_end == lock_end_before + timedelta(seconds=180)


def test_overdue_evaluation_marks_task_and_applies_default_penalty():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        with SessionLocal() as db:
            session_before = db.query(Session).filter(Session.id == session_id).first()
            lock_end_before = session_before.lock_end

        create_task = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={"title": "Overdue", "description": "Deadline test", "deadline_minutes": 5},
        )
        task_id = create_task.json()["task_id"]

        with SessionLocal() as db:
            task_row = db.query(Task).filter(Task.id == task_id).first()
            task_row.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.add(task_row)
            db.commit()

        sweep = client.post(f"/api/sessions/{session_id}/tasks/evaluate-overdue", json={})
        assert sweep.status_code == 200
        assert task_id in sweep.json()["overdue_task_ids"]

        with SessionLocal() as db:
            session_after = db.query(Session).filter(Session.id == session_id).first()
            task_row = db.query(Task).filter(Task.id == task_id).first()
            assert task_row.status == "overdue"
            expected_penalty = settings.task_overdue_default_penalty_seconds
            assert task_row.consequence_applied_seconds == expected_penalty
            assert session_after.lock_end == lock_end_before + timedelta(seconds=expected_penalty)


def test_chat_structured_output_can_create_task():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        chat_resp = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "Bitte Aufgabe: 30 Kniebeugen in 15 Minuten"},
        )
        assert chat_resp.status_code == 200

        tasks_resp = client.get(f"/api/sessions/{session_id}/tasks")
        assert tasks_resp.status_code == 200
        tasks = tasks_resp.json()["items"]
        assert len(tasks) >= 1
        assert any("Kniebeugen" in item["title"] for item in tasks)


def test_task_reward_and_penalty_events_are_logged():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        reward_task = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={"title": "Reward Event Task", "description": "done"},
        )
        reward_id = reward_task.json()["task_id"]
        completed = client.post(
            f"/api/sessions/{session_id}/tasks/{reward_id}/status",
            json={"status": "completed"},
        )
        assert completed.status_code == 200

        penalty_task = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={"title": "Penalty Event Task", "consequence_value": 180},
        )
        penalty_id = penalty_task.json()["task_id"]
        failed = client.post(
            f"/api/sessions/{session_id}/tasks/{penalty_id}/status",
            json={"status": "failed"},
        )
        assert failed.status_code == 200

        events = client.get(f"/api/sessions/{session_id}/events?source=message&limit=200")
        assert events.status_code == 200
        types = [item["event_type"] for item in events.json()["items"]]
        assert "task_reward" in types
        assert "task_penalty" in types
