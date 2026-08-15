"""
Publisher abstraction.

One implementation per platform (app/publishing/platforms/), same
registry-dispatch pattern as app.oauth (one interface, config/endpoint
differences per platform, not per-caller branching). This is the piece
that actually calls each platform's official publishing API - never
scrapes a page or automates a browser (per the spec's explicit "use
official APIs... do not scrape platforms" instruction).

Every platform's real publishing API (Graph API for Facebook/Instagram,
LinkedIn's UGC Posts API, X's v2 tweets endpoint, TikTok's Content Posting
API, YouTube Data API's videos.insert) requires that platform's app to
have been reviewed/approved for the relevant permission before it will
actually accept a real post from an arbitrary account - the same caveat
already flagged in app/oauth/platforms/*.py for the OAuth scopes
themselves. This module implements the real request shape each API
expects; getting a specific deployment's app approved to actually use it
is an operational step outside what code can verify.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


class PublishError(Exception):
    """Base class for all publish-attempt failures."""


class PublishAuthError(PublishError):
    """The stored credential was rejected - expired, revoked, or
    insufficient scope. Callers should mark the ConnectedAccount for
    reauthorization rather than retrying the same credential."""


class PublishRateLimitError(PublishError):
    """The platform rate-limited this request. Callers should retry
    later (see app/publishing/tasks.py's backoff schedule) rather than
    treating this as a permanent failure."""


class PublishContentError(PublishError):
    """The platform rejected the content itself (too long, disallowed
    media type, policy violation, etc.) - retrying the identical content
    will fail identically, so callers should not auto-retry this one."""


@dataclass
class PublishRequest:
    body: str
    media_urls: list[str]


@dataclass
class PublishResult:
    external_post_id: str
    external_post_url: str | None


class ContentPublisher(ABC):
    """One implementation per platform."""

    platform_type: str
    display_name: str

    @abstractmethod
    def publish(
        self, *, access_token: str, request: PublishRequest, transport: object | None = None
    ) -> PublishResult:
        """
        Publishes content to the platform using an already-decrypted
        access token - callers (app/publishing/tasks.py) are responsible
        for decryption via app.oauth.service.decrypt_credentials_for_publishing;
        this class never touches encrypted_credentials directly, keeping
        the "who's allowed to decrypt" surface exactly where
        app/oauth/service.py already documents it.

        transport is None in production (real network) — tests inject an
        httpx.MockTransport here instead of patching httpx.Client.post
        globally, which would also intercept FastAPI's TestClient (itself
        httpx-based). Same pattern as
        app.ai_providers.claude_provider.ClaudeProvider; see that file's
        own comment, and see the incident this fixed in
        app/tests/integration/test_scheduled_posts_api.py.

        Raises a PublishError subclass on any failure - never lets a raw
        httpx exception escape, matching the same discipline as
        app.ai_providers and app.oauth.
        """
        raise NotImplementedError
