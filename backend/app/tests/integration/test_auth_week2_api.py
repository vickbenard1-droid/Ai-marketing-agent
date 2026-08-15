"""
Integration tests for the Week 2 auth endpoints: logout, forgot/reset
password, verify-email, resend-verification. Hits the real FastAPI app via
TestClient, same pattern as test_auth_api.py.
"""
from app.core.security import generate_opaque_token, hash_opaque_token
from app.models.email_token import EmailToken, EmailTokenType
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


# --------------------------------------------------------------------------
# Logout
# --------------------------------------------------------------------------
def test_logout_returns_200(client, seeded_roles):
    resp, _ = _register(client)
    refresh_token = resp.json()["refresh_token"]

    logout_resp = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200


def test_logout_then_refresh_fails(client, seeded_roles):
    resp, _ = _register(client)
    refresh_token = resp.json()["refresh_token"]

    client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


def test_logout_with_garbage_token_still_returns_200(client):
    resp = client.post("/api/v1/auth/logout", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 200


# --------------------------------------------------------------------------
# Forgot / reset password
# --------------------------------------------------------------------------
def test_forgot_password_returns_generic_message_for_known_email(client, seeded_roles):
    _, email = _register(client)
    resp = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_forgot_password_returns_same_message_for_unknown_email(client, seeded_roles):
    known_resp, email = _register(client)
    known = client.post("/api/v1/auth/forgot-password", json={"email": email})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    # Same status and same message shape — account existence isn't leaked.
    assert known.status_code == unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]


def test_reset_password_end_to_end(client, db_session, seeded_roles):
    _, email = _register(client, password="original-password-123")
    client.post("/api/v1/auth/forgot-password", json={"email": email})

    # Simulate clicking the emailed link: pull the token row the endpoint
    # created and overwrite its hash to a raw token we control, since the
    # real raw token only ever existed in the (log-fallback) email.
    from app.models.user import User

    user = db_session.query(User).filter(User.email == email).first()
    token = (
        db_session.query(EmailToken)
        .filter(EmailToken.user_id == user.id, EmailToken.token_type == EmailTokenType.PASSWORD_RESET)
        .first()
    )
    raw_token = generate_opaque_token()
    token.token_hash = hash_opaque_token(raw_token)
    db_session.commit()

    reset_resp = client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "brand-new-password-456"}
    )
    assert reset_resp.status_code == 200

    old_login = client.post("/api/v1/auth/login", json={"email": email, "password": "original-password-123"})
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "brand-new-password-456"}
    )
    assert new_login.status_code == 200


def test_reset_password_rejects_unknown_token(client):
    resp = client.post(
        "/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "whatever123"}
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------
# Email verification
# --------------------------------------------------------------------------
def test_verify_email_end_to_end(client, db_session, seeded_roles):
    resp, email = _register(client)

    from app.models.user import User

    user = db_session.query(User).filter(User.email == email).first()
    assert user.is_email_verified is False

    token = (
        db_session.query(EmailToken)
        .filter(EmailToken.user_id == user.id, EmailToken.token_type == EmailTokenType.EMAIL_VERIFICATION)
        .first()
    )
    raw_token = generate_opaque_token()
    token.token_hash = hash_opaque_token(raw_token)
    db_session.commit()

    verify_resp = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert verify_resp.status_code == 200

    db_session.refresh(user)
    assert user.is_email_verified is True


def test_verify_email_rejects_unknown_token(client):
    resp = client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400


def test_resend_verification_returns_generic_message(client, seeded_roles):
    _, email = _register(client)
    resp = client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert resp.status_code == 200


def test_resend_verification_unknown_email_still_returns_200(client):
    resp = client.post("/api/v1/auth/resend-verification", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
