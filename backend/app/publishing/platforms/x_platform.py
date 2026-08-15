"""
X (Twitter) publisher.

Uses the v2 API's POST /2/tweets - JSON body, Bearer auth, and (unlike
the older v1.1 API) returns the tweet id directly in a nested "data"
object rather than a flat response.
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

TWEETS_URL = "https://api.twitter.com/2/tweets"


class XPublisher(ContentPublisher):
    platform_type = "x_account"
    display_name = "X"

    def publish(self, *, access_token: str, request: PublishRequest, transport: object | None = None) -> PublishResult:
        if request.media_urls:
            raise PublishContentError(
                "X media attachments require the v1.1 media/upload flow, not yet implemented — "
                "this publisher only supports text-only posts"
            )

        payload = {"text": request.body}
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=30.0, transport=transport) as client:
                response = client.post(TWEETS_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise PublishError("X publish request timed out") from exc
        except httpx.HTTPError as exc:
            raise PublishError(f"X publish request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise PublishAuthError(f"X rejected the credential ({response.status_code}): {response.text[:300]}")
        if response.status_code == 429:
            raise PublishRateLimitError("X rate-limited this request")
        if response.status_code >= 400:
            raise PublishContentError(f"X rejected the post ({response.status_code}): {response.text[:300]}")

        try:
            body = response.json()
        except ValueError as exc:
            raise PublishError("X returned a non-JSON response") from exc

        tweet_id = body.get("data", {}).get("id")
        if not tweet_id:
            raise PublishError(f"X response had no tweet id: {body}")

        return PublishResult(external_post_id=tweet_id, external_post_url=f"https://x.com/i/status/{tweet_id}")
