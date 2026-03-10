from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _register_and_finish_setup(client: TestClient, email: str = "xp-user@example.com"):
    username = f"xp-{uuid4().hex[:8]}"
    unique_email = email if email != "xp-user@example.com" else f"xp-{uuid4().hex[:8]}@example.com"

    register_resp = client.post(
        "/auth/register",
        data={
            "username": username,
            "email": unique_email,
            "password": "verysecure1",
            "password_confirm": "verysecure1",
        },
        follow_redirects=False,
    )
    assert register_resp.status_code == 303

    setup_resp = client.post(
        "/setup/complete",
        data={
            "role_style": "structured",
            "primary_goal": "Play",
            "boundary_note": "No work hours",
        },
    )
    assert setup_resp.status_code == 200


def test_experience_page_renders():
    with TestClient(app) as client:
        _register_and_finish_setup(client)
        resp = client.get("/experience")
        assert resp.status_code == 200
        html = resp.text
        assert "Onboarding" in html
        assert "xp-create-session" in html
        assert "xp-sign-contract" in html
        assert "xp-send-chat" in html
        assert "xp-chat-timeline" in html
        assert "xp-task-board" in html
        assert "xp-safety-dock" in html


def test_experience_assets_are_served():
    with TestClient(app) as client:
        js = client.get("/static/js/experience.js")
        assert js.status_code == 200
        assert "xp-create-session" in js.text
        assert "xpRenderTasks" in js.text
        assert "xp-dock-yellow" in js.text

        css = client.get("/static/css/experience.css")
        assert css.status_code == 200
        assert "xp-grid" in css.text
        assert "chat-timeline" in css.text
        assert "xp-safety-dock" in css.text
