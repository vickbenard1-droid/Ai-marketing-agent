"""
Meta Ads OAuth provider.

Distinct from app.oauth.platforms.facebook.FacebookOAuthProvider even
though both use Meta's Graph API OAuth dialog - the scopes here
(ads_management, ads_read) grant access to advertising accounts and
real ad spend, a fundamentally different (and higher-stakes) permission
surface than organic Page posting. Kept as a separate provider/platform
type rather than sharing FacebookOAuthProvider so a person connecting
organic Facebook posting is never asked to also grant ads permissions
they didn't intend to give, and vice versa.

Same token-exchange caveat as FacebookOAuthProvider: exchange_code()
returns a short-lived User Access Token; a production deployment would
additionally exchange this for a long-lived token before using it for
ongoing ad account access. Not implemented here - flagged rather than
silently incomplete, same as the organic Facebook provider's own TODO.
"""
from app.core.config import settings
from app.oauth.platforms.standard_oauth2 import StandardOAuth2Provider

GRAPH_API_VERSION = "v21.0"  # verify against Meta's current supported version before real use


class MetaAdsOAuthProvider(StandardOAuth2Provider):
    platform_type = "meta_ads"
    display_name = "Meta Ads"
    default_scopes = ["ads_management", "ads_read", "business_management"]

    authorize_base_url = f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth"
    token_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"

    def __init__(self):
        self.client_id = settings.META_ADS_CLIENT_ID
        self.client_secret = settings.META_ADS_CLIENT_SECRET
