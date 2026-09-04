"""
Sales analytics module.

The spec's 8 named metrics: leads, qualified leads, sales, conversion
rate, revenue, cost per sale, ROAS, customer acquisition cost.

cost_per_sale_cents and customer_acquisition_cost_cents deliberately
resolve to the SAME real computation (total ad spend / count of leads
reaching WON) - this app has no basis to compute them differently
(no separate non-ad acquisition cost category exists), so rather than
invent an arbitrary distinction, both spec-named metrics report the one
real number this app can actually compute, with that reasoning
surfaced explicitly via the note field rather than buried.
"""
from dataclasses import dataclass
from datetime import date as date_type
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.analytics.service import rollup_totals
from app.models.connected_account import PlatformType
from app.models.lead import Lead, LeadStage
from app.models.metric_snapshot import MetricEntityType


@dataclass
class SalesAnalytics:
    date_range: dict
    leads: int
    qualified_leads: int
    sales: int
    conversion_rate: Optional[float]
    revenue_cents: Optional[int]
    spend_cents: int
    cost_per_sale_cents: Optional[float]
    roas: Optional[float]
    customer_acquisition_cost_cents: Optional[float]
    note: str = (
        "cost_per_sale_cents and customer_acquisition_cost_cents are the same computation "
        "(total ad spend / count of leads reaching Won) — this app has no separate acquisition-cost "
        "category to compute them differently from."
    )


def compute_sales_analytics(db: Session, organization_id: uuid.UUID, *, date_start: date_type, date_stop: date_type) -> SalesAnalytics:
    leads_in_range = db.query(Lead).filter(
        Lead.organization_id == organization_id,
        Lead.created_at >= date_start,
        Lead.created_at < date_type.fromordinal(date_stop.toordinal() + 1),
    ).all()

    lead_count = len(leads_in_range)
    qualified_count = sum(1 for l in leads_in_range if l.stage in (LeadStage.QUALIFIED, LeadStage.INTERESTED, LeadStage.NEGOTIATION, LeadStage.WON))
    won_count = sum(1 for l in leads_in_range if l.stage == LeadStage.WON)

    conversion_rate = (won_count / lead_count * 100) if lead_count > 0 else None

    ad_totals = rollup_totals(db, organization_id, source=PlatformType.META_ADS, date_start=date_start, date_stop=date_stop)

    cost_per_sale = (ad_totals.spend_cents / won_count) if won_count > 0 else None
    roas = (ad_totals.revenue_cents / ad_totals.spend_cents) if ad_totals.revenue_cents is not None and ad_totals.spend_cents > 0 else None

    return SalesAnalytics(
        date_range={"start": date_start.isoformat(), "stop": date_stop.isoformat()},
        leads=lead_count, qualified_leads=qualified_count, sales=won_count, conversion_rate=conversion_rate,
        revenue_cents=ad_totals.revenue_cents, spend_cents=ad_totals.spend_cents,
        cost_per_sale_cents=cost_per_sale, roas=roas, customer_acquisition_cost_cents=cost_per_sale,
    )
