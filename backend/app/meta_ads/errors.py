"""
Meta Ads error taxonomy.

A 5-category classification (not one generic MetaApiError) because
different failures need genuinely different handling: an auth failure
means the connection needs re-authorization; a rate limit means retry
with backoff; a validation failure means the request itself was wrong
and retrying won't help; an ad-review rejection is a real, expected
outcome (not a bug) that needs to be surfaced to a person, not silently
retried or swallowed.
"""


class MetaApiError(Exception):
    """Base class - callers that don't need to distinguish categories
    can catch this; callers that do (see app/meta_ads/execution_service.py)
    catch the specific subclasses below."""


class MetaAuthError(MetaApiError):
    """The access token is invalid or expired - the connection needs
    to be re-authorized, not retried."""


class MetaPermissionError(MetaApiError):
    """The token is valid but lacks permission for this specific action
    (e.g. missing ads_management scope, or the person's role on this ad
    account doesn't allow it)."""


class MetaRateLimitError(MetaApiError):
    """Meta's API rate limit was hit - retryable with backoff."""


class MetaValidationError(MetaApiError):
    """The request itself was malformed or violates a Meta-side
    business rule (e.g. an invalid targeting spec) - retrying the exact
    same request will fail identically."""


class MetaAdReviewError(MetaApiError):
    """An ad was rejected by Meta's ad review process - a real,
    expected business outcome, not a bug in this app or in the request
    that created the ad."""
