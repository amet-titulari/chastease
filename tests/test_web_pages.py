def test_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Chastease" in response.text
    assert "Register" in response.text


def test_app_shell_page(client):
    response = client.get("/app")
    assert response.status_code == 200
    assert "Prototype App" in response.text
    assert "Login / Register" in response.text


def test_contract_page(client):
    response = client.get("/contract")
    assert response.status_code == 200
    assert "Keuschheitsvertrag" in response.text
    assert "/static/js/session.js" in response.text
    assert "/static/js/contract.js" in response.text
