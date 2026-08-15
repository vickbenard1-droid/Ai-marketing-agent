"""
Unit tests for the Week 2 auth service additions: logout/token revocation,
email verification, password reset.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.service import (
    AuthError,
    authenticate_user,
    is_refresh_token_revoked,
    issue_tokens,
    logout_user,
    register_user,
    request_password_reset,
    reset_password,
    verify_email,
)
from app.core.security import decode_token, generate_opaque_token, hash_opaque_token
from app.models.email_token import EmailToken, EmailTokenType
from app.schemas.auth import UserLogin, UserRegister
from app.tests.conftest import unique_email


def _register(db_session, seeded_roles, email=None):
    email = email or unique_email()
    return register_user(
        db_session,
        UserRegister(
            email=email, password="supersecret123", full_name="Test User", organization_name="Org"
        ),
    )


# --------------------------------------------------------------------------
# Logout / revocation
# --------------------------------------------------------------------------
def test_logout_revokes_refresh_token(db_session, seeded_roles):
    user = _register(db_session, seeded_roles)
    _, refresh_token = issue_tokens(user)
    jti = decode_token(refresh_token)["jti"]

    assert is_refresh_token_revoked(db_session, jti) is False
    logout_user(db_session, refresh_token)
    assert is_refresh_token_revoked(db_session, jti) is True


def test_logout_is_idempotent(db_session, seeded_roles):
    user = _register(db_session, seeded_roles)
    _, refresh_token = issue_tokens(user)
    logout_user(db_session, refresh_token)
    logout_user(db_session, refresh_token)  # must not raise on second call
    jti = decode_token(refresh_token)["jti"]
    assert is_refresh_token_revoked(db_session, jti) is True


def test_logout_silently_ignores_garbage_token(db_session):
    logout_user(db_session, "not-a-real-token")  # must not raise


def test_logout_silently_ignores_access_token(db_session, seeded_roles):
    user = _register(db_session, seeded_roles)
    access_token, _ = issue_tokens(user)
    logout_user(db_session, access_token)  # wrong token type — no-op, no crash
    jti = decode_token(access_token)["jti"]
    assert is_refresh_token_revoked(db_session, jti) is False


# --------------------------------------------------------------------------
# Email verification
# --------------------------------------------------------------------------
def test_register_creates_unverified_user_with_verification_token(db_session, seeded_roles):
    user = _register(db_session, seeded_roles)
    assert user.is_email_verified is False

    tokens = db_session.query(EmailToken).filter(EmailToken.user_id == user.id).all()
    assert len(tokens) == 1
    assert tokens[0].token_type == EmailTokenType.EMAIL_VERIFICATION
    assert tokens[0].used_at is None


def test_verify_email_with_valid_token_marks_user_verified(db_session, seeded_roles):
    user = _register(db_session, seeded_roles)
    token = db_session.query(EmailToken).filter(EmailToken.user_id == user.id).first()

    # The raw token isn't retrievable from the DB (only its hash is
    # stored) — reconstruct one deterministically for the test by
    # generating a fresh token and overwriting the stored hash to match,
    # which exercises the same verify_email() code path a real link click
    # would.
    raw_token = generate_opaque_token()
    token.token_hash = hash_opaque_token(raw_token)
    db_session.commit()

    verified_user = verify_email(db_session, raw_token)
    assert verified_user.is_email_verified is True


def test_verify_email_rejects_unknown_token(db_session):
    with pytest.raises(AuthError):
        verify_email(db_session, "not-a-real-token")


def test_verify_email_rejects_already_used_token(db_session, seeded_roles):
    user = _register(db_session, seeded_roles)
    token = db_session.query(EmailToken).filter(EmailToken.user_id == user.id).first()
    raw_token = generate_opaque_token()
    token.token_hash = hash_opaque_token(raw_token)
    db_session.commit()

    verify_email(db_session, raw_token)
    with pytest.raises(AuthError):
        verify_email(db_session, raw_token)


def test_verify_email_rejects_expired_token(db_session, seeded_roles):
    user = _register(db_session, seeded_roles)
    token = db_session.query(EmailToken).filter(EmailToken.user_id == user.id).first()
    raw_token = generate_opaque_token()
    token.token_hash = hash_opaque_token(raw_token)
    token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    with pytest.raises(AuthError):
        verify_email(db_session, raw_token)


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------
def test_request_password_reset_creates_token_for_known_email(db_session, seeded_roles):
    email = unique_email()
    user = _register(db_session, seeded_roles, email=email)

    request_password_reset(db_session, email)

    tokens = (
        db_session.query(EmailToken)
        .filter(EmailToken.user_id == user.id, EmailToken.token_type == EmailTokenType.PASSWORD_RESET)
        .all()
    )
    assert len(tokens) == 1


def test_request_password_reset_silently_noops_for_unknown_email(db_session):
    # Must not raise — existence of the account is never revealed.
    request_password_reset(db_session, "nobody@example.com")


def test_reset_password_with_valid_token_changes_password(db_session, seeded_roles):
    email = unique_email()
    user = _register(db_session, seeded_roles, email=email)
    request_password_reset(db_session, email)
    token = (
        db_session.query(EmailToken)
        .filter(EmailToken.user_id == user.id, EmailToken.token_type == EmailTokenType.PASSWORD_RESET)
        .first()
    )
    raw_token = generate_opaque_token()
    token.token_hash = hash_opaque_token(raw_token)
    db_session.commit()

    reset_password(db_session, raw_token, "brand-new-password-456")

    # Old password no longer works, new one does.
    with pytest.raises(AuthError):
        authenticate_user(db_session, UserLogin(email=email, password="supersecret123"))
    authenticated = authenticate_user(db_session, UserLogin(email=email, password="brand-new-password-456"))
    assert authenticated.email == email


def test_reset_password_rejects_reused_token(db_session, seeded_roles):
    email = unique_email()
    user = _register(db_session, seeded_roles, email=email)
    request_password_reset(db_session, email)
    token = (
        db_session.query(EmailToken)
        .filter(EmailToken.user_id == user.id, EmailToken.token_type == EmailTokenType.PASSWORD_RESET)
        .first()
    )
    raw_token = generate_opaque_token()
    token.token_hash = hash_opaque_token(raw_token)
    db_session.commit()

    reset_password(db_session, raw_token, "brand-new-password-456")
    with pytest.raises(AuthError):
        reset_password(db_session, raw_token, "another-password-789")


def test_reset_password_rejects_unknown_token(db_session):
    with pytest.raises(AuthError):
        reset_password(db_session, "not-a-real-token", "whatever-password-123")
