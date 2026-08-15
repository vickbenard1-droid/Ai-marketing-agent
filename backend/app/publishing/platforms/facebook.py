"""
Facebook Page publisher.

Posts to a Page's feed via Meta's Graph API (POST /{page-id}/feed for
text/link posts, POST /{page-id}/photos when media is attached - this
implementation covers the text/link case; photo/video posting uses
different endpoints and is a natural follow-up once this shape is
validated). Requires a Page Access Token (see the TODO in
app/oauth/platforms/facebook.py about exchanging for one) - a plain User
Access Token will be rejected by the Graph API for this call.
"""
import httpx

from app.oauth.platforms.facebook import GRAPH_API_VERSION
from app.publishing.base import (
    ContentPublisher,
    PublishAuthError,
    PublishContentError,
    PublishError,
    PublishRateLimitError,
    PublishRequest,
    PublishResult,
)

GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class FacebookPublisher(ContentPublisher):
    platform_type = "facebook_page"
    display_name = "Facebook"

    def publish(self, *, access_token: str, request: PublishRequest, transport: object | None = None) -> PublishResult:
        url = f"{GRAPH_API_BASE}/me/feed"
        payload = {"message": request.body, "access_token": access_token}
        if request.media_urls:
            raise PublishContentError(
                "Facebook photo/video posting requires the /photos or /videos endpoint, "
                "not yet implemented - this publisher only supports text/link posts"
            )

        try:
            with httpx.Client(timeout=30.0, transport=transport) as client:
                response = client.post(url, data=payload)
        except httpx.TimeoutException as exc:
            raise PublishError("Facebook publish request timed out") from exc
        except httpx.HTTPError as exc:
            raise PublishError(f"Facebook publish request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise PublishAuthError(
                f"Facebook rejected the credential ({response.status_code}): {response.text[:300]}"
            )
        if response.status_code == 429:
            raise PublishRateLimitError("Facebook rate-limited this request")
        if response.status_code >= 400:
            raise PublishContentError(
                f"Facebook rejected the post ({response.status_code}): {response.text[:300]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise PublishError("Facebook returned a non-JSON response") from exc

        post_id = body.get("id")
        if not post_id:
            raise PublishError(f"Facebook response had no post id: {body}")

        return PublishResult(external_post_id=post_id, external_post_url=f"https://facebook.com/{post_id}")
