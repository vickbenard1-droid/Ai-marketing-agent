"""
Website tracking service.

get_or_create_tracking_key() / regenerate_tracking_key(): a
WebsiteTrackingKey is deliberately public-facing (embedded in a
business's own website JS snippet), unlike every other credential in
this app - it identifies WHICH organization a tracking event belongs
to, not a secret granting write access to anything sensitive, so it's
safe to expose in client-side page source.

record_page_view() / record_conversion(): the two real event types a
business's website can report. record_conversion() does NOT create a
ConversionEvent directly - conversion_type_name is free text from the
tracking snippet and must be resolved against this org's real
ConversionType registry first (a webhook/snippet firing a typo'd or
not-yet-created type name should not silently create a
ConversionEvent that then can't be attributed to any real, defined
type) - that resolution happens in a separate step
(app.analytics.ingestion or a dedicated resolver), keeping this
service's own job narrow: record what the browser reported, honestly,
without fabricating a link to a ConversionType that doesn't exist.
"""
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.website_tracking_event import WebsiteTrackingEvent, WebsiteTrackingEventType
from app.models.website_tracking_key import WebsiteTrackingKey


def _generate_key() -> str:
    return f"wtk_{secrets.token_urlsafe(24)}"


def get_or_create_tracking_key(db: Session, organization_id: uuid.UUID) -> WebsiteTrackingKey:
    existing = db.query(WebsiteTrackingKey).filter(WebsiteTrackingKey.organization_id == organization_id).first()
    if existing:
        return existing
    key = WebsiteTrackingKey(organization_id=organization_id, key=_generate_key())
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def regenerate_tracking_key(db: Session, organization_id: uuid.UUID) -> WebsiteTrackingKey:
    existing = db.query(WebsiteTrackingKey).filter(WebsiteTrackingKey.organization_id == organization_id).first()
    new_key_value = _generate_key()
    if existing:
        existing.key = new_key_value
        db.commit()
        db.refresh(existing)
        return existing
    return get_or_create_tracking_key(db, organization_id)


def resolve_tracking_key(db: Session, key: str) -> Optional[uuid.UUID]:
    """Returns the organization_id this key belongs to, or None if the
    key is unrecognized - the public tracking endpoint uses this to
    authenticate an inbound event without exposing which keys exist."""
    row = db.query(WebsiteTrackingKey).filter(WebsiteTrackingKey.key == key).first()
    return row.organization_id if row else None


def record_page_view(
    db: Session, *, organization_id: uuid.UUID, visitor_id: str, page_url: Optional[str], utm_json: dict
) -> WebsiteTrackingEvent:
    event = WebsiteTrackingEvent(
        organization_id=organization_id,
        event_type=WebsiteTrackingEventType.PAGE_VIEW,
        occurred_at=datetime.now(timezone.utc),
        visitor_id=visitor_id,
        page_url=page_url,
        utm_json=utm_json or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def record_conversion(
    db: Session,
    *,
    organization_id: uuid.UUID,
    visitor_id: str,
    conversion_type_name: str,
    conversion_value_cents: Optional[int],
    page_url: Optional[str],
    utm_json: dict,
) -> WebsiteTrackingEvent:
    event = WebsiteTrackingEvent(
        organization_id=organization_id,
        event_type=WebsiteTrackingEventType.CONVERSION,
        occurred_at=datetime.now(timezone.utc),
        visitor_id=visitor_id,
        page_url=page_url,
        utm_json=utm_json or {},
        conversion_type_name=conversion_type_name,
        conversion_value_cents=conversion_value_cents,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
