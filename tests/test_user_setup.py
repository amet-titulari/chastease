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


def test_auth_register_and_login(client):
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": "auth-user",
            "email": "auth-user@example.com",
            "display_name": "Auth User",
            "password": "demo-pass-123",
        },
    )
    assert register.status_code == 200
    register_data = register.json()
    assert register_data["auth_token"]

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "auth-user", "password": "demo-pass-123"},
    )
    assert login.status_code == 200
    login_data = login.json()
    assert login_data["user_id"] == register_data["user_id"]
    assert login_data["auth_token"]

    active = client.get(
        f"/api/v1/sessions/active?user_id={register_data['user_id']}&auth_token={register_data['auth_token']}"
    )
    assert active.status_code == 200
    assert active.json()["has_active_session"] is False


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
