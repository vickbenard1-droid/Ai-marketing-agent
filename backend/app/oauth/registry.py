"""
OAuth platform registry.

Maps each organic-social PlatformType value to its provider instance -
same "one registry, dispatch by enum" pattern as
app.ai_providers.factory. get_oauth_provider() is the single place that
knows how to go from "facebook_page" to a working FacebookOAuthProvider.
"""
from app.oauth.base import OAuthNotConfiguredError, OAuthPlatformProvider
from app.oauth.platforms.facebook import FacebookOAuthProvider
from app.oauth.platforms.instagram import InstagramOAuthProvider
from app.oauth.platforms.linkedin import LinkedInOAuthProvider
from app.oauth.platforms.meta_ads import MetaAdsOAuthProvider
from app.oauth.platforms.tiktok import TikTokOAuthProvider
from app.oauth.platforms.x_platform import XOAuthProvider
from app.oauth.platforms.youtube import YouTubeOAuthProvider

_REGISTRY: dict[str, type[OAuthPlatformProvider]] = {
    "facebook_page": FacebookOAuthProvider,
    "instagram_business": InstagramOAuthProvider,
    "linkedin_page": LinkedInOAuthProvider,
    "x_account": XOAuthProvider,
    "tiktok_account": TikTokOAuthProvider,
    "youtube_channel": YouTubeOAuthProvider,
    "meta_ads": MetaAdsOAuthProvider,
}


def get_oauth_provider(platform_type: str) -> OAuthPlatformProvider:
    """
    Instantiates fresh each call (providers are cheap, stateless beyond
    their config) rather than caching singletons - avoids any question of
    stale config if settings ever change within a process lifetime (e.g.
    tests that monkeypatch settings between calls).
    """
    provider_cls = _REGISTRY.get(platform_type)
    if not provider_cls:
        raise ValueError(f"No OAuth provider registered for platform '{platform_type}'")
    return provider_cls()


def get_configured_oauth_provider(platform_type: str) -> OAuthPlatformProvider:
    """Same as get_oauth_provider, but raises OAuthNotConfiguredError up
    front if this deployment hasn't set that platform's client
    credentials - see that exception's own docstring for why this check
    happens here rather than letting the platform's own API reject an
    empty client_id."""
    provider = get_oauth_provider(platform_type)
    if not provider.is_configured():
        raise OAuthNotConfiguredError(
            f"{provider.display_name} is not configured on this deployment "
            f"(missing client ID/secret)"
        )
    return provider


def list_supported_platforms() -> list[str]:
    return list(_REGISTRY.keys())
