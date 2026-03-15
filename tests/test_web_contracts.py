from fastapi.testclient import TestClient
from uuid import uuid4

from app.config import settings
from app.main import app


def _register_admin(client: TestClient):
    email = f"contracts-{uuid4().hex[:8]}@example.com"
    existing_bootstrap = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([entry for entry in [existing_bootstrap, email] if entry])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"contracts-{uuid4().hex[:8]}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_contracts_page_and_script_are_served():
    with TestClient(app) as client:
        _register_admin(client)
        page = client.get("/contracts")
        assert page.status_code == 200
        assert "Contract View" in page.text
        assert "Admin Navigation" in page.text
        assert "contract-load-btn" in page.text

        script = client.get("/static/js/contracts.js")
        assert script.status_code == 200
        assert "Export Text" in script.text
