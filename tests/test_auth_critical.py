def test_register_returns_token_and_user_fields(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "new-user", "email": "new-user@example.com", "password": "secure-pass-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"]
    assert data["auth_token"]
    assert data["username"] == "new-user"
    assert data["email"] == "new-user@example.com"
    assert "setup_session_id" in data


def test_register_duplicate_email_returns_409(client):
    payload = {"username": "dup-email-user", "email": "dup@example.com", "password": "pass-1234"}
    client.post("/api/v1/auth/register", json=payload)
    payload2 = {"username": "other-user", "email": "dup@example.com", "password": "pass-5678"}
    response = client.post("/api/v1/auth/register", json=payload2)
    assert response.status_code == 409


def test_register_duplicate_username_returns_409(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "same-name", "email": "first@example.com", "password": "pass-1234"},
    )
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "same-name", "email": "second@example.com", "password": "pass-5678"},
    )
    assert response.status_code == 409


def test_register_whitespace_username_returns_422(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "  ", "email": "blank@example.com", "password": "pass-1234"},
    )
    assert response.status_code == 422


def test_register_invalid_email_returns_400(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "bad-email-user", "email": "not-an-email", "password": "pass-1234"},
    )
    assert response.status_code == 400


def test_login_valid_credentials_returns_token(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "login-user", "email": "login-user@example.com", "password": "my-pass-99"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "login-user", "password": "my-pass-99"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["auth_token"]
    assert data["user_id"]
    assert data["username"] == "login-user"


def test_login_wrong_password_returns_401(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "wrong-pass-user", "email": "wp@example.com", "password": "correct-pass-1"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "wrong-pass-user", "password": "wrong-pass-2"},
    )
    assert response.status_code == 401


def test_login_unknown_user_returns_401(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "ghost-user", "password": "any-pass-1"},
    )
    assert response.status_code == 401


def test_login_empty_username_returns_422(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "", "password": "any-pass-1"},
    )
    assert response.status_code == 422


def test_auth_me_valid_token_returns_user(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "me-user", "email": "me-user@example.com", "password": "pass-me-1"},
    )
    token = reg.json()["auth_token"]
    response = client.get(f"/api/v1/auth/me?auth_token={token}")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == reg.json()["user_id"]
    assert data["email"] == "me-user@example.com"


def test_auth_me_invalid_token_returns_401(client):
    response = client.get("/api/v1/auth/me?auth_token=invalid-token-xyz")
    assert response.status_code == 401


def test_login_token_is_different_from_register_token(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "token-diff-user", "email": "td@example.com", "password": "pass-td-1"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "token-diff-user", "password": "pass-td-1"},
    )
    assert reg.json()["auth_token"] != login.json()["auth_token"]


def test_login_case_insensitive_username(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "CaseUser", "email": "case@example.com", "password": "pass-case-1"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "caseuser", "password": "pass-case-1"},
    )
    assert response.status_code == 200
