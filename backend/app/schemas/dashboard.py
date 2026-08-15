"""
Dashboard summary schema (Week 2).

Every metric here is real data queried from the DB, defaulting to zero/None
when nothing exists yet — no fake/sample numbers, per the Week 2 spec. Since
campaigns, content, leads, sales, and spend have no backing tables until a
later week, those fields are hardcoded to empty-state values (0 / None) for
now with a clear docstring on why, rather than querying tables that don't
exist yet or fabricating numbers.
"""
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    business_name: str
    marketing_goal: str | None
    monthly_ad_budget: int | None
    budget_currency: str
    connected_platforms_count: int
    onboarding_completed: bool

    # Real tables for these don't exist until later weeks (Campaign,
    # Content, Lead, Sale/spend ledger) — always 0/None until then, which
    # is the correct empty state, not a placeholder to remove later.
    campaign_count: int = 0
    content_count: int = 0
    leads_count: int = 0
    sales_count: int = 0
    total_spend: float = 0.0
    spend_currency: str = "USD"
