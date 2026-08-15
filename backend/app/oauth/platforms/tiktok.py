"""
TikTok OAuth provider.

TikTok's OAuth uses "client_key" as the parameter name instead of the
more common "client_id" - a real deviation from the generic
StandardOAuth2Provider's param-building, and it applies to BOTH the
authorize URL (query params) and the token exchange (POST body) - TikTok
uses client_key consistently throughout its OAuth flow, not just at
authorization. Both exchange_code() and refresh_access_token() route
through _post_token_request(), which is overridden here to rename the
field, rather than duplicating the override in both methods. Publishing
to TikTok requires the Content Posting API scope, which - like LinkedIn's
organization scopes - needs separate application/approval from TikTok
beyond basic app registration.
"""
import httpx

from app.core.config import settings
from app.oauth.base import OAuthTokenResult
from app.oauth.platforms.standard_oauth2 import StandardOAuth2Provider


class TikTokOAuthProvider(StandardOAuth2Provider):
    platform_type = "tiktok_account"
    display_name = "TikTok"
    default_scopes = ["user.info.basic", "video.publish", "video.upload"]

    authorize_base_url = "https://www.tiktok.com/v2/auth/authorize"
    token_url = "https://open.tiktokapis.com/v2/oauth/token/"

    def __init__(self):
        self.client_id = settings.TIKTOK_CLIENT_ID
        self.client_secret = settings.TIKTOK_CLIENT_SECRET

    def build_authorize_url(self, request) -> str:
        params = {
            "client_key": request.client_id,  # TikTok-specific param name, not client_id
            "redirect_uri": request.redirect_uri,
            "response_type": "code",
            "scope": ",".join(request.scopes),  # comma-separated, not space-separated
            "state": request.state,
        }
        return f"{self.authorize_base_url}?{httpx.QueryParams(params)}"

    def _post_token_request(self, data: dict) -> OAuthTokenResult:
        # TikTok's token endpoint also expects client_key, not client_id -
        # rename the field the base class builds before sending. Both
        # exchange_code() and refresh_access_token() call this method, so
        # this single override covers both flows.
        data = dict(data)
        data["client_key"] = data.pop("client_id")
        return super()._post_token_request(data)
