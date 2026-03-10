from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _register(client: TestClient, email: str = "setup-user@example.com"):
    username = f"setup-{uuid4().hex[:8]}"
    unique_email = email if email != "setup-user@example.com" else f"setup-{uuid4().hex[:8]}@example.com"
    return client.post(
        "/auth/register",
        data={
            "username": username,
            "email": unique_email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )


def test_register_redirects_to_setup_and_setup_page_renders():
    with TestClient(app) as client:
        register_resp = _register(client)
        assert register_resp.status_code == 303
        assert register_resp.headers["location"] == "/setup"

        setup_resp = client.get("/setup")
        assert setup_resp.status_code == 200
        assert "Setup Wizard" in setup_resp.text
        assert "setup-form" in setup_resp.text


def test_setup_completion_redirects_to_experience():
    with TestClient(app) as client:
        register_resp = _register(client, email=f"complete-{uuid4().hex[:8]}@example.com")
        assert register_resp.status_code == 303
        finish_resp = client.post(
            "/setup/complete",
            data={
                "role_style": "structured",
                "primary_goal": "Mehr Konsistenz",
                "boundary_note": "Keine Aufgaben waehrend Meetings",
            },
            follow_redirects=False,
        )
        assert finish_resp.status_code == 303
        assert finish_resp.headers["location"] == "/experience"

        experience_resp = client.get("/experience")
        assert experience_resp.status_code == 200


def test_login_for_incomplete_setup_redirects_to_setup():
    with TestClient(app) as client:
        email = f"login-{uuid4().hex[:8]}@example.com"
        register_resp = _register(client, email=email)
        assert register_resp.status_code == 303
        client.post("/auth/logout")

        login_resp = client.post(
            "/auth/login",
            data={"email": email, "password": "verysecure1"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        assert login_resp.headers["location"] == "/setup"


def test_experience_redirects_to_landing_when_logged_out():
    with TestClient(app) as client:
        resp = client.get("/experience", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"
