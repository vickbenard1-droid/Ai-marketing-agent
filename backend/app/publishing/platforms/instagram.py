"""
Instagram Business publisher.

Instagram's Graph API publishing flow is genuinely two-step, unlike
Facebook's single POST: (1) create a media container (POST
/{ig-user-id}/media with image_url + caption), which returns a
container id, then (2) publish that container (POST
/{ig-user-id}/media_publish with the container id). This is a real API
shape difference, not a simplification choice - Instagram does not
support posting text-only captions with no image at all for feed posts,
so media_urls is required here, the reverse of Facebook's text-first
publisher.
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


class InstagramPublisher(ContentPublisher):
    platform_type = "instagram_business"
    display_name = "Instagram"

    def publish(self, *, access_token: str, request: PublishRequest, transport: object | None = None) -> PublishResult:
        if not request.media_urls:
            raise PublishContentError(
                "Instagram feed posts require at least one image — text-only posts aren't supported"
            )

        container_id = self._create_media_container(access_token, request, transport)
        return self._publish_container(access_token, container_id, transport)

    def _create_media_container(self, access_token: str, request: PublishRequest, transport) -> str:
        url = f"{GRAPH_API_BASE}/me/media"
        payload = {
            "image_url": request.media_urls[0],
            "caption": request.body,
            "access_token": access_token,
        }
        body = self._post(url, payload, step="container creation", transport=transport)
        container_id = body.get("id")
        if not container_id:
            raise PublishError(f"Instagram container creation response had no id: {body}")
        return container_id

    def _publish_container(self, access_token: str, container_id: str, transport) -> PublishResult:
        url = f"{GRAPH_API_BASE}/me/media_publish"
        payload = {"creation_id": container_id, "access_token": access_token}
        body = self._post(url, payload, step="publish", transport=transport)
        post_id = body.get("id")
        if not post_id:
            raise PublishError(f"Instagram publish response had no id: {body}")
        return PublishResult(external_post_id=post_id, external_post_url=None)

    def _post(self, url: str, payload: dict, *, step: str, transport=None) -> dict:
        try:
            with httpx.Client(timeout=30.0, transport=transport) as client:
                response = client.post(url, data=payload)
        except httpx.TimeoutException as exc:
            raise PublishError(f"Instagram {step} request timed out") from exc
        except httpx.HTTPError as exc:
            raise PublishError(f"Instagram {step} request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise PublishAuthError(
                f"Instagram rejected the credential during {step} ({response.status_code}): "
                f"{response.text[:300]}"
            )
        if response.status_code == 429:
            raise PublishRateLimitError(f"Instagram rate-limited the {step} request")
        if response.status_code >= 400:
            raise PublishContentError(
                f"Instagram rejected the {step} request ({response.status_code}): {response.text[:300]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise PublishError(f"Instagram {step} returned a non-JSON response") from exc
