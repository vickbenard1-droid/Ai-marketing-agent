"""
OAuth provider abstraction.

All 6 platforms this app connects to (Facebook, Instagram, LinkedIn, X,
TikTok, YouTube) use OAuth 2.0 Authorization Code flow - the exact
endpoints, scopes, and a few flow details (X requires PKCE; YouTube's
"platform" is really Google's OAuth with a YouTube-scoped consent)
differ per platform, but the shape is the same everywhere. This mirrors
app.ai_providers.base.AIProvider's pattern: one interface, one place that
knows how to build the redirect URL, exchange a code for tokens, and
refresh an expired token, implemented per-platform in
app/oauth/platforms/.

CRITICAL: nothing in this module or its implementations ever returns a
raw access/refresh token to a caller outside app/oauth/ - every function
that would naturally return one instead returns an OAuthTokenResult that
the caller immediately encrypts and stores (see
app/oauth/service.py::handle_callback). No endpoint schema in
app/schemas/connected_account.py includes a token field. This is the
concrete mechanism behind the spec's "never expose access tokens to the
frontend."
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class OAuthError(Exception):
    """Base class for all OAuth flow failures."""


class OAuthNotConfiguredError(OAuthError):
    """Raised when a platform's client_id/client_secret aren't set on
    this deployment - see app/core/config.py's own note on why this is
    checked explicitly rather than letting the platform reject an empty
    client_id with a more confusing error."""


class OAuthStateError(OAuthError):
    """Raised when the state parameter on a callback is missing, unknown,
    expired, or already used - the CSRF protection failing closed."""


class OAuthExchangeError(OAuthError):
    """Raised when exchanging an authorization code (or refresh token)
    for an access token fails - the platform rejected the request."""


@dataclass
class OAuthAuthorizeRequest:
    """What the connect-flow needs to build the redirect URL the person
    is sent to on the platform's own site."""

    client_id: str
    redirect_uri: str
    scopes: list[str]
    state: str
    # PKCE code_challenge - only used by platforms that require it (X).
    # None for platforms that don't; the base authorize-URL builder omits
    # the parameter entirely when this is None rather than sending an
    # empty one.
    code_challenge: str | None = None


@dataclass
class OAuthTokenResult:
    """Normalized token response - see module docstring for why this
    never leaves app/oauth/ except as an encrypted blob."""

    access_token: str
    refresh_token: str | None
    expires_in_seconds: int | None
    granted_scopes: list[str] = field(default_factory=list)
    # Platform-reported identity of the connected account (Page id, user
    # id, channel id) - not a secret, safe to store unencrypted on
    # ConnectedAccount.external_account_id.
    external_account_id: str | None = None
    external_account_name: str | None = None


class OAuthPlatformProvider(ABC):
    """One implementation per platform (app/oauth/platforms/*.py)."""

    platform_type: str  # matches a app.models.connected_account.PlatformType value
    display_name: str
    default_scopes: list[str]
    uses_pkce: bool = False

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this deployment has client_id/client_secret set for
        this platform. Checked before starting a connect flow - see
        OAuthNotConfiguredError."""
        raise NotImplementedError

    @abstractmethod
    def build_authorize_url(self, request: OAuthAuthorizeRequest) -> str:
        """Builds the URL the person is redirected to on the platform's
        own consent screen."""
        raise NotImplementedError

    @abstractmethod
    def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str | None = None) -> OAuthTokenResult:
        """Exchanges an authorization code for tokens. code_verifier is
        only used by platforms with uses_pkce=True."""
        raise NotImplementedError

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> OAuthTokenResult:
        """Exchanges a refresh token for a new access token. Raises
        OAuthExchangeError if the platform rejects it (e.g. the refresh
        token itself has expired or been revoked) - the caller should
        treat this the same as an unrecoverable expired connection and
        prompt full reauthorization rather than retrying the refresh."""
        raise NotImplementedError
