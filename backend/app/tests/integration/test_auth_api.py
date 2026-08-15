"""
Integration tests hitting the real FastAPI app (via TestClient) with a
SQLite-backed DB session. Exercises the HTTP layer: status codes, response
shapes, and that auth-required routes reject unauthenticated requests.
"""
from app.tests.conftest import unique_email


def _register(client, email=None, password="supersecret123"):
    email = email or unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    return resp, email


def test_register_returns_tokens(client, seeded_roles):
    resp, _ = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_register_duplicate_email_returns_400(client, seeded_roles):
    email = unique_email()
    _register(client, email=email)
    resp, _ = _register(client, email=email)
    assert resp.status_code == 400


def test_login_with_correct_credentials(client, seeded_roles):
    email = unique_email()
    _register(client, email=email, password="mypassword123")

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "mypassword123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_with_wrong_password_returns_401(client, seeded_roles):
    email = unique_email()
    _register(client, email=email, password="mypassword123")

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpassword"})
    assert resp.status_code == 401


def test_me_requires_authentication(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user_with_valid_token(client, seeded_roles):
    resp, email = _register(client)
    access_token = resp.json()["access_token"]

    me_resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["email"] == email
    assert "hashed_password" not in body  # never leak the hash


def test_refresh_issues_new_tokens(client, seeded_roles):
    resp, _ = _register(client)
    refresh_token = resp.json()["refresh_token"]

    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()


def test_refresh_rejects_access_token_used_as_refresh(client, seeded_roles):
    resp, _ = _register(client)
    access_token = resp.json()["access_token"]

    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert refresh_resp.status_code == 401


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
