from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _register_admin(client: TestClient) -> None:
    unique = uuid4().hex[:8]
    email = f"persona-htmx-{unique}@example.com"
    existing = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([item for item in [existing, email] if item])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"persona-{unique}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_personas_page_loads_htmx_partial_container():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/personas", follow_redirects=False)
        assert resp.status_code == 200
        assert "https://unpkg.com/htmx.org@1.9.12" in resp.text
        assert 'hx-get="/personas/partials/list"' in resp.text


def test_personas_partial_renders_for_admin():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/personas/partials/list", follow_redirects=False)
        assert resp.status_code == 200
        assert 'id="pm-list"' in resp.text
        assert 'hx-get="/personas/partials/list"' not in resp.text


def test_personas_partial_uses_resilient_action_hooks():
    with TestClient(app) as client:
        _register_admin(client)
        created = client.post(
            "/api/personas",
            json={
                "name": "Persona Action Test",
                "strictness_level": 3,
                "speech_style_tone": "warm",
                "speech_style_dominance": "gentle-dominant",
            },
        )
        assert created.status_code == 200
        persona_id = created.json()["id"]

        resp = client.get("/personas/partials/list", follow_redirects=False)
        assert resp.status_code == 200
        assert 'data-pm-action="edit"' in resp.text
        assert f'data-persona-id="{persona_id}"' in resp.text
        assert f'href="/api/personas/{persona_id}/export"' in resp.text
        assert 'window.pmStartEdit && window.pmStartEdit' in resp.text


def test_personas_partial_redirects_for_non_admin():
    with TestClient(app) as client:
        resp = client.get("/personas/partials/list", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
