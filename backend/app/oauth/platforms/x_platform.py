"""
X (Twitter) OAuth provider.

X's OAuth 2.0 implementation requires PKCE (RFC 7636) on every
authorization - unlike the other 5 platforms, a plain client_id +
client_secret exchange without a code_challenge/code_verifier pair is
rejected. uses_pkce=True signals this to the connect-flow (see
app/oauth/service.py::start_connect_flow), which generates and stores a
code_verifier alongside the CSRF state token and passes it back through
to exchange_code() on callback.

Confidential client authentication uses HTTP Basic (client_id:client_secret
base64-encoded in the Authorization header) rather than the client_id/
client_secret-in-body form the generic StandardOAuth2Provider posts - this
is why _post_token_request is overridden here instead of just setting
token_url/authorize_base_url like the other platforms.
"""
import base64

from app.core.config import settings
from app.oauth.platforms.standard_oauth2 import StandardOAuth2Provider


class XOAuthProvider(StandardOAuth2Provider):
    platform_type = "x_account"
    display_name = "X"
    default_scopes = ["tweet.read", "tweet.write", "users.read", "offline.access"]
    uses_pkce = True

    authorize_base_url = "https://twitter.com/i/oauth2/authorize"
    token_url = "https://api.twitter.com/2/oauth2/token"

    def __init__(self):
        self.client_id = settings.X_CLIENT_ID
        self.client_secret = settings.X_CLIENT_SECRET

    def _build_auth_headers(self) -> dict:
        # X authenticates confidential clients via HTTP Basic rather than
        # client_secret-in-body — overriding this hook (see the base
        # class) instead of duplicating _post_token_request's HTTP/error
        # handling here keeps that shared logic in one place.
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        return {"Accept": "application/json", "Authorization": f"Basic {credentials}"}

    def _build_token_request_data(self, data: dict) -> dict:
        # client_secret moves to the Authorization header above — drop it
        # from the body; client_id stays, per X's documented behavior.
        return {k: v for k, v in data.items() if k != "client_secret"}
