def test_story_turn_requires_action(client):
    response = client.post("/api/v1/story/turn", json={})
    assert response.status_code == 422


def test_story_turn_accepts_action(client):
    response = client.post("/api/v1/story/turn", json={"action": "Ich oeffne die Truhe."})
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "accepted"
