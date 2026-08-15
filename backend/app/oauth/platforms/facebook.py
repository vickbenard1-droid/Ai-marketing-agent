"""
Facebook Page OAuth provider.

Uses Meta's standard OAuth dialog + Graph API token exchange. Facebook
access tokens returned by this exchange are short-lived (~1-2 hours) User
Access Tokens; a production implementation would additionally exchange
this for a long-lived token (fb_exchange_token grant) and then fetch the
Page Access Token for the specific Page being connected via
/me/accounts, since it's the Page token - not the User token - that's
actually used to publish posts. That additional exchange is not
implemented here; see the module-level TODO below. Endpoint versions and
exact parameter names should be verified against Meta's current Graph
API docs before this is used against a real app, since Meta revises
their Graph API version numbers on a regular schedule.
"""
from app.core.config import settings
from app.oauth.platforms.standard_oauth2 import StandardOAuth2Provider

GRAPH_API_VERSION = "v21.0"  # verify against Meta's current supported version before real use


class FacebookOAuthProvider(StandardOAuth2Provider):
    platform_type = "facebook_page"
    display_name = "Facebook"
    default_scopes = ["pages_show_list", "pages_manage_posts", "pages_read_engagement"]

    authorize_base_url = f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth"
    token_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"

    def __init__(self):
        self.client_id = settings.FACEBOOK_CLIENT_ID
        self.client_secret = settings.FACEBOOK_CLIENT_SECRET

    # TODO (not implemented - flagged rather than silently incomplete):
    # after exchange_code() returns a short-lived User token, a real
    # deployment needs two more calls before publishing will work:
    #   1. GET /oauth/access_token?grant_type=fb_exchange_token&... to
    #      get a long-lived User token (~60 days)
    #   2. GET /me/accounts with that token to list the person's Pages
    #      and get each Page's own Page Access Token (long-lived, doesn't
    #      expire while the Page-User connection is active) - it's the
    #      Page token that goes into ConnectedAccount.encrypted_credentials,
    #      not the User token exchange_code() returns.
    # app/oauth/service.py currently stores whatever exchange_code()
    # returns; this is the seam where that second call would be added.
