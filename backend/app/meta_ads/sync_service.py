"""
Meta Ads sync service.

Two sync functions, each idempotent (safe to re-run):
- sync_campaign_status: pulls the real current status/budget for one
  campaign from Meta and updates the local MetaCampaign row - Meta is
  the source of truth; this never pushes local state TO Meta (that's
  execution_service's job, gated by the spend guard).
- sync_insights: pulls day-by-day performance data and upserts
  MetaInsightSnapshot rows - upsert (not insert-always) means running
  this sync twice for the same day never creates a duplicate row; it
  corrects the existing one with Meta's latest numbers instead (Meta's
  own insights can be revised for a few days after the fact - a bare
  INSERT would silently accumulate stale duplicates).
"""
import uuid
from datetime import date as date_type
from typing import Optional

from sqlalchemy.orm import Session

from app.meta_ads.meta_client import MetaMarketingClient
from app.models.meta_campaign import MetaCampaign, MetaCampaignStatus
from app.models.meta_insight_snapshot import MetaInsightEntityType, MetaInsightSnapshot


def sync_campaign_status(db: Session, *, campaign: MetaCampaign, client: MetaMarketingClient) -> MetaCampaign:
    if not campaign.external_campaign_id:
        return campaign

    remote = client.get_campaign(campaign.external_campaign_id)
    campaign.status = MetaCampaignStatus(remote["status"])
    if "daily_budget" in remote:
        campaign.daily_budget_cents = int(remote["daily_budget"])
    if "lifetime_budget" in remote:
        campaign.lifetime_budget_cents = int(remote["lifetime_budget"])
    db.commit()
    db.refresh(campaign)
    return campaign


def _extract_action_count(actions: Optional[list], action_type: str) -> Optional[int]:
    if not actions:
        return None
    for action in actions:
        if action.get("action_type") == action_type:
            try:
                return int(float(action["value"]))
            except (KeyError, ValueError, TypeError):
                return None
    return None


def _extract_action_value_cents(action_values: Optional[list], action_type: str) -> Optional[int]:
    if not action_values:
        return None
    for entry in action_values:
        if entry.get("action_type") == action_type:
            try:
                return int(round(float(entry["value"]) * 100))
            except (KeyError, ValueError, TypeError):
                return None
    return None


def sync_insights(
    db: Session,
    *,
    meta_ad_account_id: uuid.UUID,
    entity_type: MetaInsightEntityType,
    entity_id: uuid.UUID,
    external_entity_id: str,
    currency: str,
    client: MetaMarketingClient,
    date_start: str,
    date_stop: str,
) -> int:
    """Returns the count of rows written/updated."""
    rows = client.get_insights(external_entity_id, date_start=date_start, date_stop=date_stop)
    written = 0
    for row in rows:
        row_date = date_type.fromisoformat(row["date_start"])
        existing = (
            db.query(MetaInsightSnapshot)
            .filter(
                MetaInsightSnapshot.entity_type == entity_type,
                MetaInsightSnapshot.entity_id == entity_id,
                MetaInsightSnapshot.date == row_date,
            )
            .first()
        )

        spend_cents = int(round(float(row.get("spend", 0)) * 100))
        leads_count = _extract_action_count(row.get("actions"), "lead")
        purchases_count = _extract_action_count(row.get("actions"), "purchase")
        revenue_cents = _extract_action_value_cents(row.get("action_values"), "purchase")

        if existing:
            existing.impressions = int(row.get("impressions", 0))
            existing.clicks = int(row.get("clicks", 0))
            existing.spend_cents = spend_cents
            existing.reach = int(row["reach"]) if row.get("reach") is not None else None
            existing.leads_count = leads_count
            existing.purchases_count = purchases_count
            existing.revenue_cents = revenue_cents
        else:
            db.add(
                MetaInsightSnapshot(
                    meta_ad_account_id=meta_ad_account_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    date=row_date,
                    impressions=int(row.get("impressions", 0)),
                    clicks=int(row.get("clicks", 0)),
                    spend_cents=spend_cents,
                    reach=int(row["reach"]) if row.get("reach") is not None else None,
                    leads_count=leads_count,
                    purchases_count=purchases_count,
                    revenue_cents=revenue_cents,
                    currency=currency,
                )
            )
        written += 1

    db.commit()
    return written
