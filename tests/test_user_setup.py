def test_user_create_and_get(client):
    create_response = client.post(
        "/api/v1/users",
        json={"email": "user1@example.com", "display_name": "User One"},
    )
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["created"] is True
    user_id = create_data["user_id"]

    get_response = client.get(f"/api/v1/users/{user_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["email"] == "user1@example.com"
    assert get_data["display_name"] == "User One"


def test_character_create_for_user(client):
    create_user = client.post(
        "/api/v1/users",
        json={"email": "user2@example.com", "display_name": "User Two"},
    )
    user_id = create_user.json()["user_id"]

    create_character = client.post(
        f"/api/v1/users/{user_id}/characters",
        json={"name": "Main Character", "strength": 7, "intelligence": 6, "charisma": 8},
    )
    assert create_character.status_code == 200
    char_data = create_character.json()
    assert char_data["user_id"] == user_id
    assert char_data["name"] == "Main Character"
