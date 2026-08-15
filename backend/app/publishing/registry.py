"""
Publisher registry - same "one registry, dispatch by enum" pattern as
app.ai_providers.factory and app.oauth.registry.
"""
from app.publishing.base import ContentPublisher
from app.publishing.platforms.facebook import FacebookPublisher
from app.publishing.platforms.instagram import InstagramPublisher
from app.publishing.platforms.linkedin import LinkedInPublisher
from app.publishing.platforms.tiktok import TikTokPublisher
from app.publishing.platforms.x_platform import XPublisher
from app.publishing.platforms.youtube import YouTubePublisher

_REGISTRY: dict[str, type[ContentPublisher]] = {
    "facebook_page": FacebookPublisher,
    "instagram_business": InstagramPublisher,
    "linkedin_page": LinkedInPublisher,
    "x_account": XPublisher,
    "tiktok_account": TikTokPublisher,
    "youtube_channel": YouTubePublisher,
}


def get_publisher(platform_type: str) -> ContentPublisher:
    publisher_cls = _REGISTRY.get(platform_type)
    if not publisher_cls:
        raise ValueError(f"No publisher registered for platform '{platform_type}'")
    return publisher_cls()
