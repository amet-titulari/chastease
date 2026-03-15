from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _register_user(client: TestClient, prefix: str, make_admin: bool) -> None:
    unique = uuid4().hex[:8]
    email = f"{prefix}-{unique}@example.com"

    if make_admin:
        existing = settings.admin_bootstrap_emails or ""
        settings.admin_bootstrap_emails = ",".join([item for item in [existing, email] if item])

    resp = client.post(
        "/auth/register",
        data={
            "username": f"{prefix}-{unique}",
            "email": email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_non_admin_is_redirected_from_admin_pages():
    with TestClient(app) as client:
        _register_user(client, prefix="nonadmin-web", make_admin=False)
        resp = client.get("/admin", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers.get("location") == "/experience"


def test_persona_api_requires_admin_authentication():
    with TestClient(app) as client:
        unauth = client.get("/api/personas")
        assert unauth.status_code == 401

        _register_user(client, prefix="nonadmin-api-persona", make_admin=False)
        forbidden = client.get("/api/personas")
        assert forbidden.status_code == 403


def test_scenario_api_requires_admin_authentication():
    with TestClient(app) as client:
        unauth = client.get("/api/scenarios")
        assert unauth.status_code == 401

        _register_user(client, prefix="nonadmin-api-scenario", make_admin=False)
        forbidden = client.get("/api/scenarios")
        assert forbidden.status_code == 403


def test_game_posture_matrix_api_requires_admin_authentication():
    with TestClient(app) as client:
        unauth = client.get("/api/games/postures/matrix")
        assert unauth.status_code == 401

        _register_user(client, prefix="nonadmin-api-games", make_admin=False)
        forbidden = client.get("/api/games/postures/matrix")
        assert forbidden.status_code == 403
