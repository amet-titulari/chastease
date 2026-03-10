from fastapi.testclient import TestClient

from app.main import app


def _create_and_sign(client: TestClient) -> int:
    create_resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Events Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    session_id = create_resp.json()["session_id"]
    client.post(f"/api/sessions/{session_id}/sign-contract")
    return session_id


def test_session_events_aggregates_multiple_sources():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)

        client.post(f"/api/sessions/{session_id}/messages", json={"content": "Status"})
        client.post(
            f"/api/sessions/{session_id}/hygiene/openings",
            json={"duration_seconds": 120, "old_seal_number": "E-1"},
        )
        task_resp = client.post(
            f"/api/sessions/{session_id}/tasks",
            json={"title": "Event Task", "description": "Track me", "deadline_minutes": 10},
        )
        task_id = task_resp.json()["task_id"]
        client.post(f"/api/sessions/{session_id}/tasks/{task_id}/status", json={"status": "completed"})

        verify_req = client.post(
            f"/api/sessions/{session_id}/verifications/request",
            json={"requested_seal_number": "E-1"},
        )
        verification_id = verify_req.json()["verification_id"]
        client.post(
            f"/api/sessions/{session_id}/verifications/{verification_id}/upload",
            files={"file": ("proof.jpg", b"bytes", "image/jpeg")},
            data={"observed_seal_number": "E-1"},
        )
        client.post(f"/api/sessions/{session_id}/safety/safeword")

        events_resp = client.get(f"/api/sessions/{session_id}/events")
        assert events_resp.status_code == 200
        payload = events_resp.json()
        assert payload["session_id"] == session_id
        assert len(payload["items"]) >= 6

        sources = {item["source"] for item in payload["items"]}
        assert "message" in sources
        assert "safety" in sources
        assert "hygiene" in sources
        assert "task" in sources
        assert "verification" in sources


def test_session_events_filter_and_export():
    with TestClient(app) as client:
        session_id = _create_and_sign(client)
        client.post(f"/api/sessions/{session_id}/messages", json={"content": "Filter me"})

        filtered = client.get(f"/api/sessions/{session_id}/events?source=message&event_type=chat&limit=10")
        assert filtered.status_code == 200
        items = filtered.json()["items"]
        assert len(items) >= 1
        assert all(item["source"] == "message" for item in items)
        assert all(item["event_type"] == "chat" for item in items)

        export_text = client.get(f"/api/sessions/{session_id}/events/export?format=text&source=message")
        assert export_text.status_code == 200
        assert "source=message" in export_text.text

        export_json = client.get(f"/api/sessions/{session_id}/events/export?format=json&source=message")
        assert export_json.status_code == 200
        payload = export_json.json()
        assert payload["session_id"] == session_id
        assert len(payload["items"]) >= 1
