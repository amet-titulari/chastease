def _register(client, username="llm-user", password="demo-pass-123"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_llm_profile_lifecycle(client):
    auth = _register(client)
    user_id = auth["user_id"]
    token = auth["auth_token"]

    get_empty = client.get(f"/api/v1/llm/profile?user_id={user_id}&auth_token={token}")
    assert get_empty.status_code == 200
    assert get_empty.json()["configured"] is False

    create = client.post(
        "/api/v1/llm/profile",
        json={
            "user_id": user_id,
            "auth_token": token,
            "provider_name": "xai",
            "api_url": "https://api.x.ai/v1/chat/completions",
            "api_key": "super-secret-key",
            "chat_model": "grok-4-latest",
            "vision_model": "grok-4-latest",
            "behavior_prompt": "Dominant but calm.",
            "is_active": True,
        },
    )
    assert create.status_code == 200
    profile = create.json()["profile"]
    assert profile["provider_name"] == "xai"
    assert profile["has_api_key"] is True

    get_profile = client.get(f"/api/v1/llm/profile?user_id={user_id}&auth_token={token}")
    assert get_profile.status_code == 200
    loaded = get_profile.json()["profile"]
    assert loaded["chat_model"] == "grok-4-latest"
    assert loaded["behavior_prompt"] == "Dominant but calm."


def test_llm_test_dry_run(client):
    auth = _register(client, username="llm-test-user")
    user_id = auth["user_id"]
    token = auth["auth_token"]
    client.post(
        "/api/v1/llm/profile",
        json={
            "user_id": user_id,
            "auth_token": token,
            "provider_name": "custom",
            "api_url": "https://api.x.ai/v1/chat/completions",
            "api_key": "key-123",
            "chat_model": "grok-4-latest",
            "behavior_prompt": "Prompt",
            "is_active": True,
        },
    )

    test_response = client.post(
        "/api/v1/llm/test",
        json={"user_id": user_id, "auth_token": token, "dry_run": True},
    )
    assert test_response.status_code == 200
    data = test_response.json()
    assert data["ok"] is True
    assert data["dry_run"] is True
