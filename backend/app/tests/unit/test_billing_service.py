"""
Tests for app.billing.service - the Week 12 usage-limit enforcement
system, and specifically its wiring into app.ai_usage.service.generate_and_track,
the single chokepoint every real AI call in this app routes through.
"""
import pytest

import app.ai_usage.service as ai_usage_svc
import app.billing.service as billing
from app.models.ai_usage_log import AIUsageSource
from app.models.organization import Organization
from app.models.subscription_plan import SubscriptionPlan


class _RaisingFakeProvider:
    """A fake AI provider that raises if it's ever actually called - used
    to prove the limit check genuinely happens BEFORE any real (billed)
    AI call, not just that the overall operation eventually fails."""

    name = "fake"
    model = "fake-model"

    def generate(self, *args, **kwargs):
        raise AssertionError("the real provider must never be called once the token limit is exceeded")


def test_generate_and_track_blocks_before_calling_the_real_provider_when_over_limit(db_session):
    plan = SubscriptionPlan(name="free", display_name="Free", monthly_price_cents=0, max_ai_tokens_per_month=100)
    db_session.add(plan)
    db_session.flush()
    org = Organization(name="Acme", slug="acme", subscription_plan_id=plan.id)
    db_session.add(org)
    db_session.commit()

    with pytest.raises(billing.UsageLimitExceededError):
        ai_usage_svc.generate_and_track(
            db_session, _RaisingFakeProvider(), [], organization_id=org.id, actor_user_id=None,
            source=AIUsageSource.MARKETING_STRATEGY_AGENT, max_tokens=200,
        )


def test_get_plan_for_organization_fails_closed_with_no_plan_link(db_session):
    free_plan = SubscriptionPlan(name="free", display_name="Free", monthly_price_cents=0, max_campaigns=1)
    db_session.add(free_plan)
    org = Organization(name="NoPlan", slug="noplan")  # deliberately no subscription_plan_id
    db_session.add(org)
    db_session.commit()

    resolved = billing.get_plan_for_organization(db_session, org.id)
    assert resolved.name == "free"


def test_check_limit_allows_unlimited_plan_regardless_of_usage(db_session):
    agency_plan = SubscriptionPlan(name="agency", display_name="Agency", monthly_price_cents=29900, max_automated_actions_per_month=None)
    db_session.add(agency_plan)
    db_session.flush()
    org = Organization(name="BigAgency", slug="bigagency", subscription_plan_id=agency_plan.id)
    db_session.add(org)
    db_session.commit()

    billing.check_limit(db_session, organization_id=org.id, category="automated_actions", additional=10_000)


def test_check_limit_raises_when_it_would_exceed_the_real_limit(db_session):
    plan = SubscriptionPlan(name="free", display_name="Free", monthly_price_cents=0, max_campaigns=1)
    db_session.add(plan)
    db_session.flush()
    org = Organization(name="Acme2", slug="acme2", subscription_plan_id=plan.id)
    db_session.add(org)
    db_session.commit()

    from app.models.campaign import Campaign, CampaignStatus, MarketingObjective

    db_session.add(Campaign(organization_id=org.id, product_name="Existing product", objective=MarketingObjective.LEADS, desired_outcome_count=10, budget_amount=10000, budget_currency="USD", target_location="Lagos", status=CampaignStatus.DRAFT))
    db_session.commit()

    with pytest.raises(billing.UsageLimitExceededError):
        billing.check_limit(db_session, organization_id=org.id, category="campaigns", additional=1)
