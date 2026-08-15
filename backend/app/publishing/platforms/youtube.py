"""
YouTube publisher.

YouTube Data API v3's videos.insert uses Google's resumable upload
protocol: a POST to the upload endpoint with video metadata returns a
session URI in the response's Location header, and the actual video
bytes are then PUT to that URI (potentially in chunks, for large files) -
genuinely different from every other publisher in this package, all of
which send the full payload in one request. This implementation
initiates the resumable session (the metadata POST) and returns the
session URI as external_post_id, but does NOT perform the chunked byte
upload itself - that's a substantial enough piece (chunking, resuming
after a network failure mid-upload, progress tracking) to be its own
follow-up rather than something to fake here. YouTube also does not
return a real video id or watch URL until the upload+processing
completes, so external_post_url is genuinely unknown at this point, same
category of gap as TikTok's async processing.
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

UPLOAD_INIT_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"


class YouTubePublisher(ContentPublisher):
    platform_type = "youtube_channel"
    display_name = "YouTube"

    def publish(self, *, access_token: str, request: PublishRequest, transport: object | None = None) -> PublishResult:
        if not request.media_urls:
            raise PublishContentError("YouTube uploads require a video file — text-only posts aren't supported")

        title, _, description = request.body.partition("\n")
        metadata = {
            "snippet": {"title": title[:100], "description": description},
            "status": {"privacyStatus": "public"},
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/*",
        }

        try:
            with httpx.Client(timeout=30.0, transport=transport) as client:
                response = client.post(UPLOAD_INIT_URL, json=metadata, headers=headers)
        except httpx.TimeoutException as exc:
            raise PublishError("YouTube upload initiation timed out") from exc
        except httpx.HTTPError as exc:
            raise PublishError(f"YouTube upload initiation failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise PublishAuthError(f"YouTube rejected the credential ({response.status_code}): {response.text[:300]}")
        if response.status_code == 429:
            raise PublishRateLimitError("YouTube rate-limited this request")
        if response.status_code >= 400:
            raise PublishContentError(
                f"YouTube rejected the upload request ({response.status_code}): {response.text[:300]}"
            )

        session_uri = response.headers.get("location")
        if not session_uri:
            raise PublishError("YouTube response had no resumable session URI (Location header)")

        return PublishResult(external_post_id=session_uri, external_post_url=None)
