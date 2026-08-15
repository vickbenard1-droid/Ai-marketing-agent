"""
TikTok publisher.

TikTok's Content Posting API is fundamentally video-only and
asynchronous: POST /v2/post/publish/video/init/ starts an upload and
returns a publish_id immediately, but the actual post only appears after
TikTok finishes processing the uploaded video - checking completion
requires polling POST /v2/post/publish/status/fetch/ with that
publish_id. This implementation covers the init call (matching this
app's PublishResult shape, which expects a synchronous
success/external_post_id) but does NOT poll for completion - a real
deployment would need app/publishing/tasks.py to schedule a follow-up
status-check task rather than treating the init response as final. This
is a genuine architectural gap for TikTok specifically (Facebook/
Instagram/LinkedIn/X's post calls are synchronous), flagged here rather
than papered over with a fake synchronous-looking success.
"""
import httpx

from app.publishing.base import (
    ContentPublisher,
    PublishAuthError,
    PublishContentError,
    PublishError,
    PublishRateLimitError,
    PublishRequest,
    PublishResult,
)

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"


class TikTokPublisher(ContentPublisher):
    platform_type = "tiktok_account"
    display_name = "TikTok"

    def publish(self, *, access_token: str, request: PublishRequest, transport: object | None = None) -> PublishResult:
        if not request.media_urls:
            raise PublishContentError("TikTok posts require a video — this platform doesn't support text-only posts")

        payload = {
            "post_info": {"title": request.body, "privacy_level": "PUBLIC_TO_EVERYONE"},
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": request.media_urls[0],
            },
        }
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=30.0, transport=transport) as client:
                response = client.post(INIT_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise PublishError("TikTok publish request timed out") from exc
        except httpx.HTTPError as exc:
            raise PublishError(f"TikTok publish request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise PublishAuthError(f"TikTok rejected the credential ({response.status_code}): {response.text[:300]}")
        if response.status_code == 429:
            raise PublishRateLimitError("TikTok rate-limited this request")
        if response.status_code >= 400:
            raise PublishContentError(f"TikTok rejected the post ({response.status_code}): {response.text[:300]}")

        try:
            body = response.json()
        except ValueError as exc:
            raise PublishError("TikTok returned a non-JSON response") from exc

        publish_id = body.get("data", {}).get("publish_id")
        if not publish_id:
            raise PublishError(f"TikTok init response had no publish_id: {body}")

        return PublishResult(external_post_id=publish_id, external_post_url=None)
