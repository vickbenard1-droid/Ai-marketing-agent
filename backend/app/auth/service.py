"""
Auth business logic, kept separate from the API layer (app/api) so it can be
unit-tested without spinning up FastAPI, and reused later (e.g. CLI scripts).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.core.utils import slugify
from app.mail.tasks import send_email_task
from app.mail.templates import password_reset_email, verification_email
from app.models.email_token import EmailToken, EmailTokenType
from app.models.organization import Organization, OrganizationMember, Role
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.auth import UserLogin, UserRegister


class AuthError(Exception):
    """Raised for auth failures the API layer should turn into 4xx responses."""


def _is_expired(expires_at: datetime) -> bool:
    """
    Compares a token's expires_at against now, safely handling drivers that
    return naive datetimes for a `DateTime(timezone=True)` column — SQLite
    (used in tests, see app/tests/conftest.py) does this; Postgres
    (production) always returns timezone-aware values already in UTC. All
    datetimes stored by this app are UTC, so a naive value is treated as
    already-UTC rather than assumed to be local time.
    """
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def register_user(db: Session, data: UserRegister) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise AuthError("A user with this email already exists")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.flush()  # get user.id before creating dependent rows

    # Every new user gets a personal Organization they own — this is the
    # "individual user" case from the product vision. They can invite others
    # or be invited into additional orgs later.
    base_slug = slugify(data.organization_name)
    slug = base_slug
    suffix = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    org = Organization(name=data.organization_name, slug=slug)
    db.add(org)
    db.flush()

    owner_role = db.query(Role).filter(Role.name == "owner").first()
    if not owner_role:
        raise AuthError("System roles are not seeded — run the role seed script")

    membership = OrganizationMember(
        organization_id=org.id, user_id=user.id, role_id=owner_role.id
    )
    db.add(membership)
    db.commit()
    db.refresh(user)

    send_verification_email(db, user)

    return user


def authenticate_user(db: Session, data: UserLogin) -> User:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise AuthError("Incorrect email or password")
    if not user.is_active:
        raise AuthError("This account has been deactivated")
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    subject = str(user.id)
    return create_access_token(subject), create_refresh_token(subject)


def logout_user(db: Session, refresh_token: str) -> None:
    """
    Revokes a refresh token by recording its jti in the denylist (see
    app/models/revoked_token.py for why only refresh tokens, not access
    tokens, are checked this way). Silently no-ops on an already-invalid
    or already-revoked token — logout should never fail visibly to the
    caller just because the token was already gone.
    """
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return

    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return

    already_revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if already_revoked:
        return

    db.add(
        RevokedToken(
            jti=jti,
            expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        )
    )
    db.commit()


def is_refresh_token_revoked(db: Session, jti: str) -> bool:
    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None


# --------------------------------------------------------------------------
# Email verification
# --------------------------------------------------------------------------
def send_verification_email(db: Session, user: User) -> None:
    if user.is_email_verified:
        return

    raw_token = generate_opaque_token()
    db.add(
        EmailToken(
            user_id=user.id,
            token_type=EmailTokenType.EMAIL_VERIFICATION,
            token_hash=hash_opaque_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        )
    )
    db.commit()

    verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={raw_token}"
    email = verification_email(to=user.email, full_name=user.full_name or "", verify_url=verify_url)
    send_email_task.delay(
        to=email.to, subject=email.subject, text_body=email.text_body, html_body=email.html_body
    )


def verify_email(db: Session, raw_token: str) -> User:
    token_hash = hash_opaque_token(raw_token)
    token = (
        db.query(EmailToken)
        .filter(
            EmailToken.token_hash == token_hash,
            EmailToken.token_type == EmailTokenType.EMAIL_VERIFICATION,
        )
        .first()
    )
    if not token or token.used_at is not None:
        raise AuthError("This verification link is invalid or has already been used")
    if _is_expired(token.expires_at):
        raise AuthError("This verification link has expired")

    user = db.get(User, token.user_id)
    if not user:
        raise AuthError("This verification link is invalid")

    user.is_email_verified = True
    token.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------
def request_password_reset(db: Session, email: str) -> None:
    """
    Always succeeds from the caller's perspective (see
    schemas.auth.MessageResponse docstring) — whether or not the email
    matches an account is never revealed. If it does match, a reset email
    is sent; if not, this is a silent no-op.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return

    raw_token = generate_opaque_token()
    db.add(
        EmailToken(
            user_id=user.id,
            token_type=EmailTokenType.PASSWORD_RESET,
            token_hash=hash_opaque_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    db.commit()

    reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={raw_token}"
    email_content = password_reset_email(
        to=user.email, full_name=user.full_name or "", reset_url=reset_url
    )
    send_email_task.delay(
        to=email_content.to,
        subject=email_content.subject,
        text_body=email_content.text_body,
        html_body=email_content.html_body,
    )


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    token_hash = hash_opaque_token(raw_token)
    token = (
        db.query(EmailToken)
        .filter(
            EmailToken.token_hash == token_hash,
            EmailToken.token_type == EmailTokenType.PASSWORD_RESET,
        )
        .first()
    )
    if not token or token.used_at is not None:
        raise AuthError("This reset link is invalid or has already been used")
    if _is_expired(token.expires_at):
        raise AuthError("This reset link has expired")

    user = db.get(User, token.user_id)
    if not user:
        raise AuthError("This reset link is invalid")

    user.hashed_password = hash_password(new_password)
    token.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user
