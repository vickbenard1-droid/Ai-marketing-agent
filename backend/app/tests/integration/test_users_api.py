from app.tests.conftest import unique_email


def _register_and_login(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email


def test_get_my_profile(client, seeded_roles):
    headers, email = _register_and_login(client)
    resp = client.get("/api/v1/users/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == email


def test_get_my_profile_requires_auth(client):
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401


def test_update_my_profile(client, seeded_roles):
    headers, _ = _register_and_login(client)
    resp = client.patch(
        "/api/v1/users/me",
        json={"full_name": "New Name", "phone": "+1-555-0100", "timezone": "America/New_York"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["phone"] == "+1-555-0100"
    assert body["timezone"] == "America/New_York"


def test_update_my_profile_partial_update_leaves_other_fields(client, seeded_roles):
    headers, _ = _register_and_login(client)
    client.patch("/api/v1/users/me", json={"phone": "+1-555-0100"}, headers=headers)
    resp = client.patch("/api/v1/users/me", json={"timezone": "Europe/London"}, headers=headers)
    body = resp.json()
    assert body["phone"] == "+1-555-0100"  # untouched by the second request
    assert body["timezone"] == "Europe/London"


def test_change_password_with_correct_current_password(client, seeded_roles):
    email = unique_email()
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "original-password-123",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    headers = {"Authorization": f"Bearer {register_resp.json()['access_token']}"}

    resp = client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "original-password-123", "new_password": "new-password-456"},
        headers=headers,
    )
    assert resp.status_code == 200

    old_login = client.post("/api/v1/auth/login", json={"email": email, "password": "original-password-123"})
    assert old_login.status_code == 401
    new_login = client.post("/api/v1/auth/login", json={"email": email, "password": "new-password-456"})
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client, seeded_roles):
    headers, _ = _register_and_login(client)
    resp = client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "wrong-password", "new_password": "new-password-456"},
        headers=headers,
    )
    assert resp.status_code == 400
