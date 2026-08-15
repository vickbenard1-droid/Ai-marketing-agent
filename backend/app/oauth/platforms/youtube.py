"""
YouTube Channel OAuth provider.

"YouTube" from an OAuth perspective is Google's standard OAuth 2.0 (the
same identity platform used for Gmail, Google Ads, GA4, etc.) scoped down
to YouTube-specific permissions via the requested scopes - there is no
YouTube-specific authorize/token endpoint. access_type=offline and
prompt=consent are added on top of the generic authorize URL because
Google only issues a refresh_token on the first consent grant by
default; without these, a reconnect after a person has already
authorized once would silently return no refresh_token, breaking the
reauthorize flow this app's spec explicitly requires.
"""
import httpx

from app.core.config import settings
from app.oauth.platforms.standard_oauth2 import StandardOAuth2Provider


class YouTubeOAuthProvider(StandardOAuth2Provider):
    platform_type = "youtube_channel"
    display_name = "YouTube"
    default_scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]

    authorize_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"

    def __init__(self):
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET

    def build_authorize_url(self, request) -> str:
        params = {
            "client_id": request.client_id,
            "redirect_uri": request.redirect_uri,
            "response_type": "code",
            "scope": " ".join(request.scopes),
            "state": request.state,
            "access_type": "offline",  # required to receive a refresh_token at all
            "prompt": "consent",  # required to receive one on every (re)connect, not just the first
        }
        return f"{self.authorize_base_url}?{httpx.QueryParams(params)}"
