"""
Billing / usage-limit service.

get_current_usage() computes REAL usage by counting real rows - never a
cached/estimated counter that could drift from reality, same discipline
as every other counting mechanism in this app (e.g.
app.optimization.safety's real daily-action-count query). check_limit()
is the one function every enforcement call site uses; it fails CLOSED
on a genuinely ambiguous state (no plan resolvable at all) by falling
back to the Free tier's limits, never to "no limit" - the safer
direction to err in for a paid-usage-limiting system.

Monthly usage windows are calendar-month, UTC, from the 1st of the
current month through now - not a rolling 30-day window - matching how
subscription billing periods are conventionally understood.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai_usage_log import AIUsageLog
from app.models.automated_action_log import AutomatedActionLog
from app.models.campaign import Campaign
from app.models.connected_account import ConnectedAccount, ConnectionStatus
from app.models.content import Content
from app.models.organization import Organization
from app.models.subscription_plan import SubscriptionPlan

UsageCategory = str  # one of: "ai_tokens", "campaigns", "connected_accounts", "content_generations", "automated_actions"


@dataclass
class UsageSnapshot:
    category: UsageCategory
    current: int
    limit: Optional[int]  # None means unlimited


class UsageLimitExceededError(Exception):
    pass


def _current_month_start() -> datetime:
    today = date.today()
    return datetime(today.year, today.month, 1, tzinfo=timezone.utc)


def get_plan_for_organization(db: Session, organization_id: uuid.UUID) -> SubscriptionPlan:
    """Fails closed: an organization with no resolvable plan (null
    subscription_plan_id, or a plan row that's been deactivated) gets
    treated as Free-tier limits, never as unlimited."""
    org = db.get(Organization, organization_id)
    if org and org.subscription_plan_id:
        plan = db.get(SubscriptionPlan, org.subscription_plan_id)
        if plan and plan.is_active:
            return plan

    free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == "free").first()
    if not free_plan:
        raise RuntimeError("No 'free' SubscriptionPlan exists — run app.db.seed_plans before serving real traffic")
    return free_plan


def get_current_usage(db: Session, organization_id: uuid.UUID) -> dict:
    month_start = _current_month_start()

    ai_tokens = (
        db.query(func.coalesce(func.sum(AIUsageLog.input_tokens + AIUsageLog.output_tokens), 0))
        .filter(AIUsageLog.organization_id == organization_id, AIUsageLog.created_at >= month_start, AIUsageLog.succeeded.is_(True))
        .scalar()
        or 0
    )
    campaigns = db.query(func.count(Campaign.id)).filter(Campaign.organization_id == organization_id).scalar() or 0
    connected_accounts = (
        db.query(func.count(ConnectedAccount.id))
        .filter(ConnectedAccount.organization_id == organization_id, ConnectedAccount.status == ConnectionStatus.CONNECTED)
        .scalar()
        or 0
    )
    content_generations = (
        db.query(func.count(Content.id))
        .filter(Content.organization_id == organization_id, Content.created_at >= month_start)
        .scalar()
        or 0
    )
    automated_actions = (
        db.query(func.count(AutomatedActionLog.id))
        .filter(AutomatedActionLog.organization_id == organization_id, AutomatedActionLog.executed_at >= month_start)
        .scalar()
        or 0
    )

    return {
        "ai_tokens": ai_tokens,
        "campaigns": campaigns,
        "connected_accounts": connected_accounts,
        "content_generations": content_generations,
        "automated_actions": automated_actions,
    }


_LIMIT_FIELD_BY_CATEGORY = {
    "ai_tokens": "max_ai_tokens_per_month",
    "campaigns": "max_campaigns",
    "connected_accounts": "max_connected_accounts",
    "content_generations": "max_content_generations_per_month",
    "automated_actions": "max_automated_actions_per_month",
}


def get_usage_snapshot(db: Session, organization_id: uuid.UUID) -> list:
    plan = get_plan_for_organization(db, organization_id)
    usage = get_current_usage(db, organization_id)
    return [UsageSnapshot(category=cat, current=usage[cat], limit=getattr(plan, field)) for cat, field in _LIMIT_FIELD_BY_CATEGORY.items()]


def check_limit(db: Session, *, organization_id: uuid.UUID, category: UsageCategory, additional: int = 1) -> None:
    """
    Raises UsageLimitExceededError if performing `additional` more units
    of `category` usage would exceed the organization's real current
    plan limit. A limit of None (unlimited) always passes. Real call
    sites call this BEFORE performing the action being limited (e.g.
    before generating content, before connecting another account),
    never after — this is a gate, not an after-the-fact audit.
    """
    if category not in _LIMIT_FIELD_BY_CATEGORY:
        raise ValueError(f"Unknown usage category: {category!r}")

    plan = get_plan_for_organization(db, organization_id)
    limit = getattr(plan, _LIMIT_FIELD_BY_CATEGORY[category])
    if limit is None:
        return

    usage = get_current_usage(db, organization_id)
    projected = usage[category] + additional
    if projected > limit:
        raise UsageLimitExceededError(
            f"This would bring '{category}' usage to {projected}, exceeding the {plan.display_name} plan's limit of {limit}. "
            f"Upgrade the plan or reduce usage."
        )
