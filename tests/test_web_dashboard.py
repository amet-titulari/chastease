from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_renders():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert "Chastease Test Console" in html
        assert "create-session-form" in html
        assert "chat-send-btn" in html
        assert "task-create-btn" in html
        assert "task-evaluate-overdue-btn" in html
        assert "task-fail-btn" in html


def test_dashboard_script_is_served():
    with TestClient(app) as client:
        resp = client.get("/static/js/dashboard.js")
        assert resp.status_code == 200
        assert "Session erstellt" in resp.text
