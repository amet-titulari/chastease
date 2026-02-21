def test_setup_demo_page(client):
    response = client.get("/api/v1/setup/demo", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app"
