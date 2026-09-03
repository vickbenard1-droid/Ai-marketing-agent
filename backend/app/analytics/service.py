"""
Core analytics service.

rollup_totals() is the SINGLE function that sums real MetricSnapshot
rows into a RawTotals - every dashboard, the AI analytics agent, and
any other analytics-facing code in this app calls this one function
rather than each writing its own SQL, so the exact same "how do we sum
across sources/entities/dates" logic is used everywhere, and a future
fix to that logic only needs to happen in one place.

seed_default_conversion_types() creates 5 spec-named conversion types
for an org if it has none yet - idempotent (safe to call on every
request), never overwrites a business's own customizations if they've
already created/edited their conversion types.
"""
import uuid
from datetime import date as date_type
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.metrics import RawTotals
from app.models.connected_account import PlatformType
from app.models.conversion_type import ConversionCategory, ConversionType
from app.models.metric_snapshot import MetricEntityType, MetricSnapshot

_DEFAULT_CONVERSION_TYPES = [
    {"name": "Lead", "category": ConversionCategory.LEAD, "counts_as_revenue": False},
    {"name": "Qualified Lead", "category": ConversionCategory.QUALIFICATION, "counts_as_revenue": False},
    {"name": "Appointment", "category": ConversionCategory.ENGAGEMENT, "counts_as_revenue": False},
    {"name": "Purchase", "category": ConversionCategory.PURCHASE, "counts_as_revenue": True},
    {"name": "Subscription", "category": ConversionCategory.SUBSCRIPTION, "counts_as_revenue": True},
]


class AnalyticsError(Exception):
    """Raised for analytics-service failures the API layer should turn into 4xx responses."""


def rollup_totals(
    db: Session,
    organization_id: uuid.UUID,
    *,
    source: Optional[PlatformType] = None,
    entity_type: Optional[MetricEntityType] = None,
    entity_id: Optional[uuid.UUID] = None,
    date_start: date_type,
    date_stop: date_type,
) -> RawTotals:
    """
    Sums real MetricSnapshot rows into one RawTotals. leads_count/
    purchases_count/revenue_cents stay None (via SQL SUM's own NULL
    passthrough on an all-NULL group) rather than being coerced to 0,
    preserving the unmeasured-vs-zero distinction all the way from raw
    storage into the derived-metric layer.
    """
    query = db.query(
        func.coalesce(func.sum(MetricSnapshot.impressions), 0),
        func.coalesce(func.sum(MetricSnapshot.clicks), 0),
        func.coalesce(func.sum(MetricSnapshot.spend_cents), 0),
        func.sum(MetricSnapshot.leads_count),
        func.sum(MetricSnapshot.purchases_count),
        func.sum(MetricSnapshot.revenue_cents),
        func.sum(MetricSnapshot.reach),
    ).filter(
        MetricSnapshot.organization_id == organization_id,
        MetricSnapshot.date >= date_start,
        MetricSnapshot.date <= date_stop,
    )
    if source is not None:
        query = query.filter(MetricSnapshot.source == source)
    if entity_type is not None:
        query = query.filter(MetricSnapshot.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(MetricSnapshot.entity_id == entity_id)

    row = query.first()
    impressions, clicks, spend_cents, leads_count, purchases_count, revenue_cents, reach = row
    return RawTotals(
        impressions=impressions or 0,
        clicks=clicks or 0,
        spend_cents=spend_cents or 0,
        leads_count=leads_count,
        purchases_count=purchases_count,
        revenue_cents=revenue_cents,
        reach=reach,
    )


def seed_default_conversion_types(db: Session, organization_id: uuid.UUID) -> list:
    existing = db.query(ConversionType).filter(ConversionType.organization_id == organization_id).first()
    if existing:
        return db.query(ConversionType).filter(ConversionType.organization_id == organization_id).all()

    created = []
    for spec in _DEFAULT_CONVERSION_TYPES:
        ct = ConversionType(organization_id=organization_id, **spec)
        db.add(ct)
        created.append(ct)
    db.commit()
    for ct in created:
        db.refresh(ct)
    return created


def list_conversion_types(db: Session, organization_id: uuid.UUID, *, active_only: bool = True) -> list:
    query = db.query(ConversionType).filter(ConversionType.organization_id == organization_id)
    if active_only:
        query = query.filter(ConversionType.is_active.is_(True))
    return query.all()


def create_conversion_type(
    db: Session,
    *,
    organization_id: uuid.UUID,
    name: str,
    category: ConversionCategory,
    description: Optional[str] = None,
    counts_as_revenue: bool = False,
) -> ConversionType:
    existing = (
        db.query(ConversionType)
        .filter(ConversionType.organization_id == organization_id, ConversionType.name == name)
        .first()
    )
    if existing:
        raise AnalyticsError(f"A conversion type named '{name}' already exists for this organization")

    ct = ConversionType(
        organization_id=organization_id, name=name, category=category, description=description, counts_as_revenue=counts_as_revenue
    )
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return ct
