from fastapi.testclient import TestClient

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
