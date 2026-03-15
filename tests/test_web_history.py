from fastapi.testclient import TestClient
from uuid import uuid4

from app.config import settings
from app.main import app


def _register_admin(client: TestClient):
    email = f"history-{uuid4().hex[:8]}@example.com"
    existing_bootstrap = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([entry for entry in [existing_bootstrap, email] if entry])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"history-{uuid4().hex[:8]}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_history_page_and_script_are_served():
    with TestClient(app) as client:
        _register_admin(client)
        page = client.get("/history")
        assert page.status_code == 200
        assert "Session History" in page.text
        assert "Admin Navigation" in page.text
        assert "history-load-btn" in page.text

        script = client.get("/static/js/history.js")
        assert script.status_code == 200
        assert "Export Text" in script.text
