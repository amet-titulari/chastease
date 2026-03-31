from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _register_admin(client: TestClient) -> None:
    unique = uuid4().hex[:8]
    email = f"scenario-htmx-{unique}@example.com"
    existing = settings.admin_bootstrap_emails or ""
    settings.admin_bootstrap_emails = ",".join([item for item in [existing, email] if item])
    resp = client.post(
        "/auth/register",
        data={
            "username": f"scenario-{unique}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_scenarios_page_loads_htmx_partial_container():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/scenarios", follow_redirects=False)
        assert resp.status_code == 200
        assert "/static/js/ui_common.js" in resp.text
        assert "/static/js/ui_runtime.js" in resp.text
        assert "/static/js/scenarios.js" in resp.text
        assert "https://unpkg.com/htmx.org@1.9.12" in resp.text
        assert 'hx-get="/scenarios/partials/list"' in resp.text


def test_scenarios_partial_renders_for_admin():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/scenarios/partials/list", follow_redirects=False)
        assert resp.status_code == 200
        assert 'id="sm-list"' in resp.text
        assert 'hx-get="/scenarios/partials/list"' not in resp.text


def test_scenarios_page_contains_edit_flow_hooks():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/scenarios", follow_redirects=False)
        assert resp.status_code == 200
        assert 'id="sm-form-panel"' in resp.text
        assert 'id="sm-title"' in resp.text
        assert 'id="sm-key"' in resp.text
        assert "/static/js/ui_runtime.js" in resp.text
        assert "/static/js/scenarios.js" in resp.text


def test_scenarios_page_contains_phase_target_editor_fields():
    with TestClient(app) as client:
        _register_admin(client)
        resp = client.get("/scenarios", follow_redirects=False)
        assert resp.status_code == 200
        html = resp.text
        assert 'id="sm-phases-editor"' in html
        assert 'id="sm-add-phase-btn"' in html
        assert 'id="sm-add-lore-btn"' in html
        assert "/static/js/scenarios.js" in html


def test_scenarios_partial_uses_delegated_actions_instead_of_inline_onclick():
    with TestClient(app) as client:
        _register_admin(client)
        created = client.post(
            "/api/scenarios",
            json={
                "title": "Delegated Action Scenario",
                "key": "delegated_action_scenario",
                "summary": "delegated",
                "lorebook": [],
                "phases": [],
                "tags": [],
            },
        )
        assert created.status_code == 200
        scenario_id = created.json()["id"]

        resp = client.get("/scenarios/partials/list", follow_redirects=False)
        assert resp.status_code == 200
        assert 'onclick=' not in resp.text
        assert f'data-sm-action="edit"' in resp.text
        assert f'data-scenario-id="{scenario_id}"' in resp.text


def test_scenarios_partial_redirects_for_non_admin():
    with TestClient(app) as client:
        resp = client.get("/scenarios/partials/list", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
