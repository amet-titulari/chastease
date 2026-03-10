from fastapi.testclient import TestClient

from app.main import app


def test_contracts_page_and_script_are_served():
    with TestClient(app) as client:
        page = client.get("/contracts")
        assert page.status_code == 200
        assert "Contract View" in page.text
        assert "contract-load-btn" in page.text

        script = client.get("/static/js/contracts.js")
        assert script.status_code == 200
        assert "Export Text" in script.text
