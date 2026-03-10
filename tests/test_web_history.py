from fastapi.testclient import TestClient

from app.main import app


def test_history_page_and_script_are_served():
    with TestClient(app) as client:
        page = client.get("/history")
        assert page.status_code == 200
        assert "Session History" in page.text
        assert "history-load-btn" in page.text

        script = client.get("/static/js/history.js")
        assert script.status_code == 200
        assert "Export Text" in script.text
