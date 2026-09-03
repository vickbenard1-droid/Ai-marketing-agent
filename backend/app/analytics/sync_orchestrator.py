"""
Sync orchestrator.

Bridges every real data source into the unified MetricSnapshot table -
Week 7's MetaInsightSnapshot rows, plus the normalized rows
app.analytics.ingestion's translators produce for Google Ads/GA4/
Shopify/WooCommerce - all funnel through upsert_metric_snapshot(), the
one function permitted to write a MetricSnapshot row, so every source's
sync path gets the identical "correct the existing row for this
(source, entity, date), never silently accumulate a duplicate" guarantee
Week 7's own sync_service established for Meta insights specifically.

sync_meta_insights_for_organization() is the concrete bridge from Week
7's own MetaInsightSnapshot table into this week's unified
MetricSnapshot table - Week 7's table is NOT replaced or deprecated (it
remains the source of truth for Meta-specific fields like entity_type
distinguishing campaign/ad_set/ad), this orchestrator reads from it and
writes a corresponding, source=META_ADS MetricSnapshot row so Meta data
participates in the same unified rollups/dashboards as every other
source.
"""
import uuid
from datetime import date as date_type
from typing import Optional

from sqlalchemy.orm import Session

from app.models.connected_account import PlatformType
from app.models.meta_insight_snapshot import MetaInsightSnapshot
from app.models.metric_snapshot import MetricEntityType, MetricSnapshot


def upsert_metric_snapshot(
    db: Session,
    *,
    organization_id: uuid.UUID,
    source: PlatformType,
    entity_type: MetricEntityType,
    entity_id: Optional[uuid.UUID],
    date: date_type,
    impressions: int = 0,
    clicks: int = 0,
    spend_cents: int = 0,
    leads_count: Optional[int] = None,
    purchases_count: Optional[int] = None,
    revenue_cents: Optional[int] = None,
    reach: Optional[int] = None,
    currency: str = "USD",
) -> MetricSnapshot:
    existing = (
        db.query(MetricSnapshot)
        .filter(
            MetricSnapshot.organization_id == organization_id,
            MetricSnapshot.source == source,
            MetricSnapshot.entity_type == entity_type,
            MetricSnapshot.entity_id == entity_id,
            MetricSnapshot.date == date,
        )
        .first()
    )
    if existing:
        existing.impressions = impressions
        existing.clicks = clicks
        existing.spend_cents = spend_cents
        existing.leads_count = leads_count
        existing.purchases_count = purchases_count
        existing.revenue_cents = revenue_cents
        existing.reach = reach
        existing.currency = currency
        db.commit()
        db.refresh(existing)
        return existing

    snapshot = MetricSnapshot(
        organization_id=organization_id,
        source=source,
        entity_type=entity_type,
        entity_id=entity_id,
        date=date,
        impressions=impressions,
        clicks=clicks,
        spend_cents=spend_cents,
        leads_count=leads_count,
        purchases_count=purchases_count,
        revenue_cents=revenue_cents,
        reach=reach,
        currency=currency,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def sync_meta_insights_for_organization(db: Session, organization_id: uuid.UUID) -> int:
    """
    Bridges every MetaInsightSnapshot row (Week 7) whose entity is a
    CAMPAIGN into a corresponding MetricSnapshot row - ad-set and ad
    level insights are Meta-specific detail this unified table doesn't
    need to duplicate (campaign level is what every cross-source
    dashboard/rollup this app builds actually compares against).
    Returns the count of MetricSnapshot rows written/updated.
    """
    from app.models.meta_ad_account import MetaAdAccount
    from app.models.meta_campaign import MetaCampaign

    campaign_ids_for_org = {
        c.id
        for c in db.query(MetaCampaign)
        .join(MetaAdAccount, MetaAdAccount.id == MetaCampaign.meta_ad_account_id)
        .filter(MetaAdAccount.organization_id == organization_id)
        .all()
    }
    if not campaign_ids_for_org:
        return 0

    from app.models.meta_insight_snapshot import MetaInsightEntityType

    rows = (
        db.query(MetaInsightSnapshot)
        .filter(
            MetaInsightSnapshot.entity_type == MetaInsightEntityType.CAMPAIGN,
            MetaInsightSnapshot.entity_id.in_(campaign_ids_for_org),
        )
        .all()
    )

    written = 0
    for row in rows:
        upsert_metric_snapshot(
            db,
            organization_id=organization_id,
            source=PlatformType.META_ADS,
            entity_type=MetricEntityType.CAMPAIGN,
            entity_id=row.entity_id,
            date=row.date,
            impressions=row.impressions,
            clicks=row.clicks,
            spend_cents=row.spend_cents,
            leads_count=row.leads_count,
            purchases_count=row.purchases_count,
            revenue_cents=row.revenue_cents,
            reach=row.reach,
            currency=row.currency,
        )
        written += 1
    return written
