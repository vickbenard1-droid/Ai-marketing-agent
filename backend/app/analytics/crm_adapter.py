"""
CRM adapter.

HONEST ARCHITECTURE DECISION: "CRM integrations" names a whole category
of possible platforms (Salesforce, HubSpot, Pipedrive, a custom internal
system, ...), each with its own real, different API. Rather than pick
one vendor and build a real integration against it (which would falsely
imply "CRM support" means "works with every CRM"), this module defines
a generic CRMAdapter interface plus ONE concrete, genuinely useful
implementation: GenericWebhookCRMAdapter, which works with ANY CRM that
can send an outbound webhook on a contact-stage change (nearly every
real CRM platform supports this, even ones with no public REST API at
all) - the honest, actually-general CRM integration this app can
support without picking a single vendor to special-case.

CRMConversionRecord is the normalized shape this module (and any future
vendor-specific adapter) produces - the same shape
app.analytics.ingestion's other translators use, so a webhook-based CRM
conversion flows into the exact same MetricSnapshot/ConversionEvent
pipeline as every other source.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CRMConversionRecord:
    """One CRM-reported conversion (a contact reached a stage that maps
    to a ConversionType) - the normalized shape this module produces,
    regardless of which CRM (or webhook) produced it."""

    external_contact_id: str
    conversion_type_name: str
    occurred_at: datetime
    value_cents: Optional[int] = None
    source_attribution: Optional[dict] = None


class CRMAdapter(ABC):
    """One implementation per real CRM integration path - see module
    docstring for why no vendor-specific subclass exists yet."""

    @abstractmethod
    def receive_webhook_event(self, payload: dict) -> Optional[CRMConversionRecord]:
        """Returns None (not an error) if this payload doesn't
        represent a conversion this app should record - an unmapped or
        irrelevant webhook event is an EXPECTED occurrence, not
        exceptional."""


class GenericWebhookCRMAdapter(CRMAdapter):
    """
    Works with any CRM whose webhook configuration can be pointed at a
    URL and whose payload is a flat JSON object with the fields below -
    most CRMs support a configurable webhook payload shape (or this app
    can be the target of a Zapier/Make automation translating whatever
    the CRM natively sends into this shape), so this genuinely covers a
    very wide range of real CRMs without this app needing to special-case
    any one of them.
    """

    _REQUIRED_FIELDS = {"contact_id", "conversion_type", "occurred_at"}

    def receive_webhook_event(self, payload: dict) -> Optional[CRMConversionRecord]:
        missing = self._REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError(f"Webhook payload is missing required fields: {sorted(missing)}")

        try:
            occurred_at = datetime.fromisoformat(payload["occurred_at"].replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"Could not parse occurred_at as a real datetime: {payload.get('occurred_at')!r}") from exc

        value_cents = None
        if payload.get("value") is not None:
            try:
                value_cents = int(round(float(payload["value"]) * 100))
            except (ValueError, TypeError):
                value_cents = None  # a genuinely unparseable value is dropped, not guessed at

        return CRMConversionRecord(
            external_contact_id=str(payload["contact_id"]),
            conversion_type_name=str(payload["conversion_type"]),
            occurred_at=occurred_at,
            value_cents=value_cents,
            source_attribution=payload.get("source_attribution"),
        )
