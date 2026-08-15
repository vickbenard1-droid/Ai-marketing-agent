"""
Security primitives used across the app:
- Password hashing (argon2, via passlib)
- JWT access/refresh token creation & decoding
- Symmetric encryption for third-party credentials (ConnectedAccount)

Nothing in this file should ever be imported by frontend-facing code paths
that could leak secrets — this is backend-only by construction (Python).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# --------------------------------------------------------------------------
# JWT tokens
# --------------------------------------------------------------------------
TokenType = Literal["access", "refresh"]


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),  # unique token id, useful for future revocation lists
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# --------------------------------------------------------------------------
# Credential encryption (for ConnectedAccount.encrypted_credentials)
# --------------------------------------------------------------------------
def _get_fernet() -> Fernet:
    if not settings.CREDENTIALS_ENCRYPTION_KEY:
        raise RuntimeError(
            "CREDENTIALS_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and set it in .env"
        )
    return Fernet(settings.CREDENTIALS_ENCRYPTION_KEY.encode())


def encrypt_secret(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> Optional[str]:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None


# --------------------------------------------------------------------------
# Opaque single-use tokens (email verification, password reset)
# --------------------------------------------------------------------------
# Not JWTs on purpose — see app/models/email_token.py docstring. The raw
# token is what goes in the emailed link; only its SHA-256 hash is ever
# stored, so a DB read never hands out a working link.
import hashlib
import secrets


def generate_opaque_token() -> str:
    """URL-safe random token, sent to the user (email link) — never stored."""
    return secrets.token_urlsafe(32)


def hash_opaque_token(raw_token: str) -> str:
    """SHA-256 hex digest — what actually gets stored/compared in the DB."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
