"""
LinkedIn Page publisher.

Uses the UGC Posts API (POST /v2/ugcPosts) - LinkedIn's REST-ish JSON
body shape rather than form-encoded (a real, notable difference from the
Graph API family above). The "author" field must be the organization's
URN (urn:li:organization:{id}), which comes from
ConnectedAccount.external_account_id - see the TODO below for where that
gets populated, mirroring the same Page-id-population gap flagged in
app/oauth/platforms/facebook.py.
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

UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"


class LinkedInPublisher(ContentPublisher):
    platform_type = "linkedin_page"
    display_name = "LinkedIn"

    # TODO: author_urn should come from the ConnectedAccount this publish
    # call is for (external_account_id, populated when the LinkedIn
    # OAuth flow is extended to fetch the organization URN post-connect -
    # not yet implemented, same gap as Facebook/Instagram's Page token
    # exchange). Passed as a parameter here rather than hardcoded so the
    # real caller (app/publishing/tasks.py) has an explicit place to wire
    # it once that's built.
    def publish(
        self,
        *,
        access_token: str,
        request: PublishRequest,
        author_urn: str | None = None,
        transport: object | None = None,
    ) -> PublishResult:
        if not author_urn:
            raise PublishError(
                "LinkedIn publishing requires the connected organization's URN, "
                "which isn't populated for this account yet"
            )

        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": request.body},
                    "shareMediaCategory": "NONE" if not request.media_urls else "IMAGE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30.0, transport=transport) as client:
                response = client.post(UGC_POSTS_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise PublishError("LinkedIn publish request timed out") from exc
        except httpx.HTTPError as exc:
            raise PublishError(f"LinkedIn publish request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise PublishAuthError(
                f"LinkedIn rejected the credential ({response.status_code}): {response.text[:300]}"
            )
        if response.status_code == 429:
            raise PublishRateLimitError("LinkedIn rate-limited this request")
        if response.status_code >= 400:
            raise PublishContentError(
                f"LinkedIn rejected the post ({response.status_code}): {response.text[:300]}"
            )

        post_urn = response.headers.get("x-restli-id")
        if not post_urn:
            raise PublishError("LinkedIn response had no x-restli-id header with the post URN")

        return PublishResult(external_post_id=post_urn, external_post_url=None)
