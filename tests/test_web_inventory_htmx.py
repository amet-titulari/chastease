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
        assert 'data-im-inline-form' in resp.text


def test_inventory_partial_renders_for_admin():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/inventory/partials/list", follow_redirects=False)
        assert resp.status_code == 200
        assert 'id="im-list"' in resp.text
        assert 'hx-get="/inventory/partials/list"' not in resp.text


def test_inventory_partial_escapes_item_name_inside_onclick_actions():
    with TestClient(app) as client:
        _register_admin(client)
        created = client.post(
            "/api/inventory/items",
            json={
                "key": "quote_test",
                "name": 'Foo "Bar"',
                "category": "test",
                "description": "desc",
                "tags": [],
                "is_active": True,
            },
        )
        assert created.status_code == 200
        item_id = created.json()["id"]

        resp = client.get("/inventory/partials/list", follow_redirects=False)
        assert resp.status_code == 200
        assert f'data-im-action="export"' in resp.text
        assert f'data-item-id="{item_id}"' in resp.text
        assert f'href="/api/inventory/items/{item_id}/export"' in resp.text
        assert 'window.imStartEdit && window.imStartEdit' in resp.text
        assert 'Foo &#34;Bar&#34;' in resp.text or 'Foo "Bar"' in resp.text


def test_inventory_item_detail_endpoint_returns_owned_item_for_edit_flow():
    with TestClient(app) as client:
        _register_admin(client)
        created = client.post(
            "/api/inventory/items",
            json={
                "key": "detail_test",
                "name": "Detail Test",
                "category": "device",
                "description": "desc",
                "tags": ["alpha"],
                "is_active": True,
            },
        )
        assert created.status_code == 200
        item_id = created.json()["id"]

        resp = client.get(f"/api/inventory/items/{item_id}")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["id"] == item_id
        assert payload["name"] == "Detail Test"
        assert payload["category"] == "device"


def test_inventory_partial_redirects_for_non_admin():
    with TestClient(app) as client:
        resp = client.get("/inventory/partials/list", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
