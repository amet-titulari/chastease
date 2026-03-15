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
        resp = client.get("/admin/operations")
        assert resp.status_code == 200
        html = resp.text
        assert "Operations" in html
        assert "Session-Historie" in html
        assert "Vertragspruefung" in html
        assert 'id="admin-menu"' in html


def test_landing_has_no_testconsole_shortcut():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "/testconsole" not in resp.text


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
