from chastease.api.routers import ttlock as ttlock_router


def _register(client, username, name="Wearer", password="demo-pass-123", email=None):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "display_name": name,
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_ttlock_discover_returns_locks_and_gateways(client, monkeypatch):
    async def _fake_token(**_kwargs):
        return "access-token"

    monkeypatch.setattr(ttlock_router, "_obtain_token", _fake_token)

    async def _fake_locks(**_kwargs):
        return [{"lockId": 12345, "lockAlias": "Front Door"}]

    async def _fake_gateways(**_kwargs):
        return [{"gatewayId": 9876, "gatewayName": "Main Gateway"}]

    monkeypatch.setattr(ttlock_router, "_list_locks", _fake_locks)
    monkeypatch.setattr(ttlock_router, "_list_gateways", _fake_gateways)
    client.app.state.config.TTL_CLIENT_ID = "demo-client"
    client.app.state.config.TTL_CLIENT_SECRET = "demo-secret"

    auth = _register(client, "ttlock-discover-user", "TTLock User")

    response = client.post(
        "/api/v1/setup/ttlock/discover",
        json={
            "user_id": auth["user_id"],
            "auth_token": auth["auth_token"],
            "ttl_user": "wearer@example.com",
            "ttl_pass": "secret-pass",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["locks"][0]["lockId"] == "12345"
    assert data["locks"][0]["lockAlias"] == "Front Door"
    assert data["gateways"][0]["gatewayId"] == "9876"
    assert data["gateways"][0]["gatewayName"] == "Main Gateway"
    assert len(data["ttl_pass_md5"]) == 32


def test_ttlock_discover_requires_valid_user_token(client, monkeypatch):
    client.app.state.config.TTL_CLIENT_ID = "demo-client"
    client.app.state.config.TTL_CLIENT_SECRET = "demo-secret"
    auth = _register(client, "ttlock-discover-user-2", "TTLock User 2")

    response = client.post(
        "/api/v1/setup/ttlock/discover",
        json={
            "user_id": auth["user_id"],
            "auth_token": "invalid-token",
            "ttl_user": "wearer@example.com",
            "ttl_pass": "secret-pass",
        },
    )
    assert response.status_code == 401
