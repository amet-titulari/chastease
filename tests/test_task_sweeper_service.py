from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.session import Session
from app.models.task import Task
from app.services.task_sweeper import sweep_overdue_tasks_for_active_sessions


def test_sweeper_marks_overdue_and_applies_penalty():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/sessions",
            json={
                "persona_name": "Sweep Persona",
                "player_nickname": "Wearer",
                "min_duration_seconds": 300,
                "max_duration_seconds": 900,
            },
        )
        session_id = create_resp.json()["session_id"]
        client.post(f"/api/sessions/{session_id}/sign-contract")

        with SessionLocal() as db:
            session_row = db.query(Session).filter(Session.id == session_id).first()
            lock_end_before = session_row.lock_end
            task = Task(
                session_id=session_id,
                title="Background overdue",
                status="pending",
                deadline_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id

        result = sweep_overdue_tasks_for_active_sessions()
        assert result["scanned_sessions"] >= 1
        assert result["affected_sessions"] >= 1
        assert result["changed_tasks"] >= 1

        with SessionLocal() as db:
            session_after = db.query(Session).filter(Session.id == session_id).first()
            task_after = db.query(Task).filter(Task.id == task_id).first()
            assert task_after.status == "overdue"
            assert task_after.consequence_applied_seconds == 300
            assert session_after.lock_end == lock_end_before + timedelta(seconds=300)
