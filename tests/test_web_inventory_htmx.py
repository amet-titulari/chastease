from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _register_admin(client: TestClient) -> None:
    unique = uuid4().hex[:8]
    email = f"inventory-htmx-{unique}@example.com"
    existing = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([item for item in [existing, email] if item])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"inventory-{unique}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_inventory_page_loads_htmx_partial_container():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/inventory", follow_redirects=False)
        assert resp.status_code == 200
        assert "https://unpkg.com/htmx.org@1.9.12" in resp.text
        assert 'hx-get="/inventory/partials/list"' in resp.text


def test_inventory_partial_renders_for_admin():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/inventory/partials/list", follow_redirects=False)
        assert resp.status_code == 200
        assert 'id="im-list"' in resp.text
        assert 'hx-get="/inventory/partials/list"' in resp.text


def test_inventory_partial_redirects_for_non_admin():
    with TestClient(app) as client:
        resp = client.get("/inventory/partials/list", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
