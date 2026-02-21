def test_setup_demo_page(client):
    response = client.get("/api/v1/setup/demo")
    assert response.status_code == 200
    assert "Setup Prototype Demo" in response.text
