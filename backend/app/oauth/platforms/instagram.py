"""
Instagram Business OAuth provider.

Instagram Business/Creator accounts are connected via Meta's Graph API
(the same OAuth dialog as Facebook - there is no separate "Instagram
OAuth" for business accounts, only the legacy Basic Display API which
doesn't support publishing and is being phased out by Meta). An Instagram
Business account must be linked to a Facebook Page, and posting happens
through that Page's connection - see the same TODO as facebook.py
regarding exchanging for a long-lived Page token, which applies here
identically. Kept as its own PlatformType/provider (rather than folded
into FacebookOAuthProvider) because a business may connect one without
the other, and the scopes requested differ (Instagram needs
instagram_basic + instagram_content_publish in addition to the Page
scopes).
"""
from app.core.config import settings
from app.oauth.platforms.facebook import GRAPH_API_VERSION
from app.oauth.platforms.standard_oauth2 import StandardOAuth2Provider


class InstagramOAuthProvider(StandardOAuth2Provider):
    platform_type = "instagram_business"
    display_name = "Instagram"
    default_scopes = [
        "instagram_basic",
        "instagram_content_publish",
        "pages_show_list",
        "pages_read_engagement",
    ]

    authorize_base_url = f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth"
    token_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"

    def __init__(self):
        self.client_id = settings.INSTAGRAM_CLIENT_ID
        self.client_secret = settings.INSTAGRAM_CLIENT_SECRET
