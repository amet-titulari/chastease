from fastapi.testclient import TestClient
from uuid import uuid4

from app.config import settings
from app.main import app


def _register_admin(client: TestClient):
    email = f"dash-{uuid4().hex[:8]}@example.com"
    existing_bootstrap = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([entry for entry in [existing_bootstrap, email] if entry])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"dash-{uuid4().hex[:8]}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_landing_page_renders_auth_ui():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert "Willkommen im Ritualraum" in html
        assert "/auth/register" in html
        assert "/auth/login" in html


def test_dashboard_renders():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/testconsole")
        assert resp.status_code == 200
        html = resp.text
        assert "Chastease" in html
        assert "create-session-form" in html
        assert "timer-remaining" in html
        assert "session-events-btn" in html
        assert "timer-status-btn" in html
        assert "timer-freeze-btn" in html
        assert "chat-send-btn" in html
        assert "admin-secret" in html
        assert "chat-ws-connect-btn" in html
        assert "chat-ws-rotate-token-btn" in html
        assert "task-create-btn" in html
        assert "task-evaluate-overdue-btn" in html
        assert "task-fail-btn" in html
        assert "persona-preset-select" in html
        assert "apply-persona-preset-btn" in html
        assert "push-subscribe-btn" in html
        assert "push-list-btn" in html
        assert "push-test-btn" in html
        assert "hygiene-quota-btn" in html
        assert "hygiene_limit_daily" in html


def test_dashboard_script_is_served():
    with TestClient(app) as client:
        resp = client.get("/static/js/dashboard.js")
        assert resp.status_code == 200
        assert "Session erstellt" in resp.text


def test_stylesheet_contains_responsive_rules():
    with TestClient(app) as client:
        resp = client.get("/static/css/style.css")
        assert resp.status_code == 200
        assert "@media (max-width: 680px)" in resp.text
        assert "grid-template-columns: 1fr" in resp.text


def test_history_route_exists():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/history")
        assert resp.status_code == 200
