"""
Generic OAuth 2.0 Authorization Code flow.

Implements the standard exchange (RFC 6749 section 4.1) once, as a base
every per-platform provider subclasses - each platform subclass only
needs to supply its own endpoints, scopes, and how to parse the
platform-specific bits of the token/identity response (see each file in
this package). This is the "config-driven" seam mentioned in
app/oauth/base.py's docstring: most of what differs between
Facebook/LinkedIn/TikTok/YouTube is data (URLs, scope strings, JSON field
names), not logic.

httpx.Client is used directly here (not app.ai_providers, which is a
different kind of external call) - token exchange is a one-shot POST with
no streaming, retries, or provider-swapping needed, so the lighter-weight
direct approach fits better than reusing the AI-provider abstraction for
an unrelated kind of HTTP call.
"""
import httpx

from app.oauth.base import OAuthExchangeError, OAuthPlatformProvider, OAuthTokenResult


class StandardOAuth2Provider(OAuthPlatformProvider):
    """
    Subclasses must set: platform_type, display_name, default_scopes,
    client_id, client_secret, authorize_base_url, token_url. Subclasses
    may override _parse_token_response() if a platform's token response
    has non-standard field names (most don't) and should override
    fetch_account_identity() to populate external_account_id/name from
    that platform's own "who am I" endpoint, since OAuth 2.0 itself
    doesn't standardize that.
    """

    authorize_base_url: str
    token_url: str
    client_id: str
    client_secret: str

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def build_authorize_url(self, request) -> str:
        params = {
            "client_id": request.client_id,
            "redirect_uri": request.redirect_uri,
            "response_type": "code",
            "scope": " ".join(request.scopes),
            "state": request.state,
        }
        if request.code_challenge:
            params["code_challenge"] = request.code_challenge
            params["code_challenge_method"] = "S256"
        return f"{self.authorize_base_url}?{httpx.QueryParams(params)}"

    def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str | None = None) -> OAuthTokenResult:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        return self._post_token_request(data)

    def refresh_access_token(self, refresh_token: str) -> OAuthTokenResult:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        return self._post_token_request(data)

    def _build_auth_headers(self) -> dict:
        """Extension hook — override to add/replace headers used for
        client authentication (see XOAuthProvider, which uses HTTP Basic
        instead of body fields). Default: standard Accept header only."""
        return {"Accept": "application/json"}

    def _build_token_request_data(self, data: dict) -> dict:
        """Extension hook — override to modify the outgoing form body
        (see XOAuthProvider, which drops client_secret once it's moved
        into the Authorization header). Default: pass through unchanged."""
        return data

    def _post_token_request(self, data: dict) -> OAuthTokenResult:
        data = self._build_token_request_data(data)
        headers = self._build_auth_headers()
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(self.token_url, data=data, headers=headers)
        except httpx.TimeoutException as exc:
            raise OAuthExchangeError(f"{self.display_name} token request timed out") from exc
        except httpx.HTTPError as exc:
            raise OAuthExchangeError(f"{self.display_name} token request failed: {exc}") from exc

        if response.status_code >= 400:
            raise OAuthExchangeError(
                f"{self.display_name} rejected the token request "
                f"({response.status_code}): {response.text[:300]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise OAuthExchangeError(
                f"{self.display_name} returned a non-JSON token response"
            ) from exc

        return self._parse_token_response(body)

    def _parse_token_response(self, body: dict) -> OAuthTokenResult:
        access_token = body.get("access_token")
        if not access_token:
            raise OAuthExchangeError(
                f"{self.display_name} token response had no access_token: {body}"
            )
        scope_str = body.get("scope", "")
        granted_scopes = scope_str.split() if isinstance(scope_str, str) else list(scope_str or [])
        return OAuthTokenResult(
            access_token=access_token,
            refresh_token=body.get("refresh_token"),
            expires_in_seconds=body.get("expires_in"),
            granted_scopes=granted_scopes,
        )
