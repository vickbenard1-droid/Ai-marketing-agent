"""
Unit tests for app.core.security: password hashing and JWT tokens.
No DB or FastAPI app required.
"""
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_password_hash_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token(subject="user-123")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_has_refresh_type():
    token = create_refresh_token(subject="user-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_decode_token_rejects_garbage():
    assert decode_token("not-a-real-jwt") is None


def test_access_and_refresh_tokens_are_distinct_and_not_interchangeable():
    access = create_access_token(subject="user-1")
    refresh = create_refresh_token(subject="user-1")
    assert access != refresh
    assert decode_token(access)["type"] != decode_token(refresh)["type"]
