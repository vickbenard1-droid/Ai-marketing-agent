"""
OAuth orchestration service.

This is where the pieces in app/oauth/base.py, app/oauth/registry.py, and
app/models/oauth_state.py come together into the actual connect flow the
spec asks for: connect -> authorize -> see connected account -> disconnect
-> reauthorize.

Security properties this module is responsible for (see each function's
docstring for how):
- CSRF: the state parameter is a random, single-use, short-lived,
  server-validated token (app.models.oauth_state.OAuthState) - a callback
  with an unknown, expired, or already-used state is rejected outright.
- Token secrecy: raw access/refresh tokens exist in memory only inside
  this module's own call stack. They are immediately encrypted (see
  app.core.security.encrypt_secret) before being stored on
  ConnectedAccount.encrypted_credentials, and this module never returns
  a decrypted token to its callers - see decrypt_credentials_for_publishing()
  for the one narrow, internal-only exception (used by the publishing
  pipeline, never by an API response).
"""
import base64
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret
from app.models.connected_account import ConnectedAccount, ConnectionStatus
from app.models.oauth_state import OAuthState
from app.oauth.base import (
    OAuthAuthorizeRequest,
    OAuthError,
    OAuthExchangeError,
    OAuthStateError,
)
from app.oauth.registry import get_configured_oauth_provider, get_oauth_provider

STATE_EXPIRY_MINUTES = 15  # long enough for a person to complete the platform's consent screen


class OAuthFlowError(Exception):
    """Raised for connect-flow failures the API layer should turn into 4xx responses."""


def list_connected_accounts(db: Session, organization_id: uuid.UUID) -> list[ConnectedAccount]:
    return (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.organization_id == organization_id,
            ConnectedAccount.status != ConnectionStatus.DISCONNECTED,
        )
        .order_by(ConnectedAccount.created_at.desc())
        .all()
    )


def get_connected_account(
    db: Session, *, organization_id: uuid.UUID, account_id: uuid.UUID
) -> ConnectedAccount:
    account = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.id == account_id, ConnectedAccount.organization_id == organization_id)
        .first()
    )
    if not account:
        raise OAuthFlowError("Connected account not found")
    return account


def _generate_pkce_pair() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge) per RFC 7636 - verifier is
    a random string, challenge is its SHA-256 hash, base64url-encoded
    without padding."""
    verifier = secrets.token_urlsafe(64)[:128]  # RFC 7636 allows 43-128 chars
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _build_redirect_uri(platform_type: str) -> str:
    return f"{settings.OAUTH_REDIRECT_BASE_URL}/api/v1/oauth/{platform_type}/callback"


def start_connect_flow(
    db: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    initiated_by_user_id: uuid.UUID,
    platform_type: str,
) -> str:
    """
    Returns the authorize URL the frontend should redirect the person to.
    Raises OAuthFlowError (wrapping OAuthNotConfiguredError) if this
    deployment hasn't configured the platform's client credentials.
    """
    try:
        provider = get_configured_oauth_provider(platform_type)
    except OAuthError as exc:
        raise OAuthFlowError(str(exc)) from exc

    state_value = secrets.token_urlsafe(32)
    code_verifier, code_challenge = (_generate_pkce_pair() if provider.uses_pkce else (None, None))

    oauth_state = OAuthState(
        state_value=state_value,
        organization_id=organization_id,
        project_id=project_id,
        initiated_by_user_id=initiated_by_user_id,
        platform_type=platform_type,
        code_verifier=code_verifier,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=STATE_EXPIRY_MINUTES),
    )
    db.add(oauth_state)
    db.commit()

    request = OAuthAuthorizeRequest(
        client_id=provider.client_id,
        redirect_uri=_build_redirect_uri(platform_type),
        scopes=provider.default_scopes,
        state=state_value,
        code_challenge=code_challenge,
    )
    return provider.build_authorize_url(request)


def _is_expired(expires_at: datetime) -> bool:
    """
    Compares a stored expires_at against now, safely handling drivers
    (SQLite, notably) that don't round-trip tzinfo through
    DateTime(timezone=True) — a naive datetime read back from such a
    driver is still UTC (that's what was written), it just lost the
    tzinfo marker, so this treats naive as UTC rather than raising or
    silently comparing incompatible datetimes. Same fix as
    app.auth.service._is_expired; replicated here rather than imported
    across domains for a two-line helper.
    """
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def _consume_state(db: Session, *, platform_type: str, state_value: str) -> OAuthState:
    """
    Looks up and invalidates a state token in one step. Every failure
    mode (missing, expired, already used, or platform mismatch) raises
    the same OAuthStateError with a generic message - deliberately not
    distinguishing "expired" from "unknown" from "reused" in the error
    surfaced to the caller, since telling an attacker *why* their forged
    state was rejected is free information they shouldn't get.
    """
    record = db.query(OAuthState).filter(OAuthState.state_value == state_value).first()

    if (
        not record
        or record.used_at is not None
        or _is_expired(record.expires_at)
        or record.platform_type != platform_type
    ):
        raise OAuthStateError("Invalid or expired OAuth state")

    record.used_at = datetime.now(timezone.utc)
    db.commit()
    return record


def handle_callback(
    db: Session,
    *,
    platform_type: str,
    state_value: str,
    code: str,
) -> ConnectedAccount:
    """
    The callback handler: validates state (CSRF check - see
    _consume_state), exchanges the authorization code for tokens,
    encrypts them, and creates or updates the ConnectedAccount row.
    Never returns anything containing the raw token - the returned
    ConnectedAccount's encrypted_credentials field holds only ciphertext,
    and the API layer's response schema (see
    app/schemas/connected_account.py::ConnectedAccountPublic) doesn't
    even include that field.
    """
    try:
        oauth_state = _consume_state(db, platform_type=platform_type, state_value=state_value)
    except OAuthStateError as exc:
        raise OAuthFlowError(str(exc)) from exc

    try:
        provider = get_configured_oauth_provider(platform_type)
    except OAuthError as exc:
        raise OAuthFlowError(str(exc)) from exc

    try:
        token_result = provider.exchange_code(
            code=code,
            redirect_uri=_build_redirect_uri(platform_type),
            code_verifier=oauth_state.code_verifier,
        )
    except OAuthExchangeError as exc:
        raise OAuthFlowError(f"Failed to complete {provider.display_name} connection: {exc}") from exc

    expires_at = None
    if token_result.expires_in_seconds:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_result.expires_in_seconds)

    credentials_blob = encrypt_secret(
        json.dumps(
            {"access_token": token_result.access_token, "refresh_token": token_result.refresh_token}
        )
    )

    # One ConnectedAccount per (org, project, platform) - reconnecting an
    # already-connected platform updates the existing row rather than
    # creating a duplicate, so a business doesn't accumulate stale rows
    # every time they reauthorize.
    existing = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.organization_id == oauth_state.organization_id,
            ConnectedAccount.project_id == oauth_state.project_id,
            ConnectedAccount.platform == platform_type,
        )
        .first()
    )

    account = existing or ConnectedAccount(
        organization_id=oauth_state.organization_id,
        project_id=oauth_state.project_id,
        platform=platform_type,
    )
    account.status = ConnectionStatus.CONNECTED
    account.encrypted_credentials = credentials_blob
    account.token_expires_at = expires_at
    account.granted_scopes = " ".join(token_result.granted_scopes) if token_result.granted_scopes else None
    account.external_account_id = token_result.external_account_id
    account.external_account_name = token_result.external_account_name
    account.last_error = None

    if not existing:
        db.add(account)
    db.flush()

    write_audit_log(
        db,
        organization_id=oauth_state.organization_id,
        actor_user_id=oauth_state.initiated_by_user_id,
        action="connected_account.connected",
        resource_type="ConnectedAccount",
        resource_id=str(account.id),
        metadata={"platform": platform_type},
    )

    db.commit()
    db.refresh(account)
    return account


def disconnect_account(
    db: Session, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, account_id: uuid.UUID
) -> ConnectedAccount:
    """
    Marks the account disconnected and discards the stored credentials
    entirely (not just marks them inactive) - once disconnected, there's
    no path back to the old token without a fresh OAuth flow, which is
    the correct behavior: a disconnected account shouldn't retain a live,
    usable credential sitting encrypted in the database indefinitely.
    """
    account = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.id == account_id, ConnectedAccount.organization_id == organization_id)
        .first()
    )
    if not account:
        raise OAuthFlowError("Connected account not found")

    account.status = ConnectionStatus.DISCONNECTED
    account.encrypted_credentials = None
    account.token_expires_at = None
    account.granted_scopes = None

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="connected_account.disconnected",
        resource_type="ConnectedAccount",
        resource_id=str(account.id),
        metadata={"platform": account.platform.value},
    )

    db.commit()
    db.refresh(account)
    return account


def decrypt_credentials_for_publishing(account: ConnectedAccount) -> dict | None:
    """
    The ONE place in this codebase allowed to decrypt a stored token -
    called only by the publishing pipeline (app/publishing/tasks.py),
    never by an API endpoint. Returns {"access_token": ..., "refresh_token":
    ...} or None if the account has no credentials or decryption fails
    (e.g. the encryption key rotated without a migration - see
    app.core.security.decrypt_secret's own None-on-failure contract).
    """
    if not account.encrypted_credentials:
        return None
    plaintext = decrypt_secret(account.encrypted_credentials)
    if not plaintext:
        return None
    return json.loads(plaintext)


def reauthorize_account(
    db: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    initiated_by_user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> str:
    """
    Starts a fresh connect flow for an existing (expired/errored)
    account. Returns the authorize URL, same as start_connect_flow - this
    is not a token refresh (see refresh_expired_account for that); this
    is for the case where refresh itself fails or isn't available and the
    only way forward is a full re-consent by the person.
    """
    account = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.id == account_id, ConnectedAccount.organization_id == organization_id)
        .first()
    )
    if not account:
        raise OAuthFlowError("Connected account not found")

    return start_connect_flow(
        db,
        organization_id=organization_id,
        project_id=project_id,
        initiated_by_user_id=initiated_by_user_id,
        platform_type=account.platform.value,
    )


def refresh_expired_account(db: Session, account: ConnectedAccount) -> bool:
    """
    Attempts a silent token refresh using the stored refresh_token, for
    platforms/accounts that have one. Returns True on success (account
    updated in place, still CONNECTED), False if refresh isn't possible
    or fails (account marked EXPIRED, needs reauthorize_account instead).
    Called by the publishing pipeline before a scheduled publish attempt
    against an account whose token_expires_at has passed - see
    app/publishing/tasks.py.
    """
    creds = decrypt_credentials_for_publishing(account)
    if not creds or not creds.get("refresh_token"):
        account.status = ConnectionStatus.EXPIRED
        db.commit()
        return False

    try:
        provider = get_oauth_provider(account.platform.value)
        result = provider.refresh_access_token(creds["refresh_token"])
    except OAuthError as exc:
        account.status = ConnectionStatus.EXPIRED
        account.last_error = str(exc)
        db.commit()
        return False

    expires_at = None
    if result.expires_in_seconds:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=result.expires_in_seconds)

    account.encrypted_credentials = encrypt_secret(
        json.dumps(
            {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token or creds.get("refresh_token"),
            }
        )
    )
    account.token_expires_at = expires_at
    account.status = ConnectionStatus.CONNECTED
    account.last_error = None
    db.commit()
    return True
