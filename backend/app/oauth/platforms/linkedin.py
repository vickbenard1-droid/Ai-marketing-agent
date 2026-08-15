"""
LinkedIn OAuth provider.

Standard OAuth 2.0 (LinkedIn's "Sign In with LinkedIn using OpenID
Connect" plus the Marketing/Community Management scopes needed to post on
behalf of an organization Page). w_organization_social is the scope that
grants posting-as-a-Page; w_member_social would post as the individual
member instead - this app requests the organization scope since the spec
targets business Pages, not personal profiles. Note LinkedIn's Marketing
API access (including w_organization_social) requires the app to be
approved for the relevant API product, not just registered - a detail
worth surfacing in onboarding copy for whoever configures this
deployment's LinkedIn app.
"""
from app.core.config import settings
from app.oauth.platforms.standard_oauth2 import StandardOAuth2Provider


class LinkedInOAuthProvider(StandardOAuth2Provider):
    platform_type = "linkedin_page"
    display_name = "LinkedIn"
    default_scopes = ["w_organization_social", "r_organization_social", "rw_organization_admin"]

    authorize_base_url = "https://www.linkedin.com/oauth/v2/authorization"
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"

    def __init__(self):
        self.client_id = settings.LINKEDIN_CLIENT_ID
        self.client_secret = settings.LINKEDIN_CLIENT_SECRET
