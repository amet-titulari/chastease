from fastapi.testclient import TestClient

from app.main import app


def _create_session(client: TestClient) -> int:
    resp = client.post(
        "/api/sessions",
        json={
            "persona_name": "Push Persona",
            "player_nickname": "Wearer",
            "min_duration_seconds": 300,
            "max_duration_seconds": 900,
        },
    )
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_push_subscription_crud_flow():
    with TestClient(app) as client:
        session_id = _create_session(client)

        upsert = client.post(
            f"/api/sessions/{session_id}/push/subscriptions",
            json={
                "endpoint": "https://example.invalid/push/123",
                "keys": {"p256dh": "abc", "auth": "def"},
                "user_agent": "pytest",
            },
        )
        assert upsert.status_code == 200
        sub_id = upsert.json()["subscription_id"]

        listed = client.get(f"/api/sessions/{session_id}/push/subscriptions")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == sub_id

        deleted = client.delete(f"/api/sessions/{session_id}/push/subscriptions/{sub_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


def test_push_test_reports_not_configured_by_default():
    with TestClient(app) as client:
        session_id = _create_session(client)

        client.post(
            f"/api/sessions/{session_id}/push/subscriptions",
            json={
                "endpoint": "https://example.invalid/push/456",
                "keys": {"p256dh": "ghi", "auth": "jkl"},
            },
        )

        resp = client.post(f"/api/sessions/{session_id}/push/test", json={})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["subscriptions"] == 1
        assert payload["dispatch"]["enabled"] is False
