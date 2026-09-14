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


def test_automated_actions_billing_limit_is_a_genuine_third_independent_layer(db_session):
    """
    Real proof, not just an architectural claim: constructs a scenario
    where Week 7's spend guard and Week 9's own autonomy safety checks
    (assert_can_execute_autonomously) would BOTH pass - genuinely
    permissive whitelist, autonomy settings, and a real configured
    AdAccountSpendLimit - and confirms the Week 12 billing limit still
    blocks the autonomous action as a real, independent third layer.
    """
    import app.optimization.execution as execution
    from app.models.ai_usage_log import AIUsageSource  # noqa: F401
    from app.models.campaign_autonomy_settings import AutonomyLevel, CampaignAutonomySettings, CampaignWhitelist
    from app.models.meta_ad_account import MetaAdAccount
    from app.models.meta_campaign import MetaCampaign, MetaCampaignObjective, MetaCampaignStatus
    from app.models.ad_account_spend_limit import AdAccountSpendLimit
    from app.models.optimization_decision import DecisionRisk, DecisionStatus, OptimizationActionType, OptimizationDecision
    from app.models.user import User
    import uuid

    org = Organization(name="AutoActionsOrg", slug="autoactionsorg")
    db_session.add(org)
    db_session.flush()
    user = User(email="autoactions@example.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    ad_account = MetaAdAccount(organization_id=org.id, connected_account_id=uuid.uuid4(), external_ad_account_id="act_x", name="Test", currency="USD", timezone_name="UTC")
    db_session.add(ad_account)
    db_session.flush()
    campaign = MetaCampaign(organization_id=org.id, meta_ad_account_id=ad_account.id, name="Test", objective=MetaCampaignObjective.OUTCOME_SALES, external_campaign_id="c1", status=MetaCampaignStatus.ACTIVE, daily_budget_cents=1000)
    db_session.add(campaign)
    db_session.commit()

    free_plan = SubscriptionPlan(name="free", display_name="Free", monthly_price_cents=0, max_automated_actions_per_month=0)
    db_session.add(free_plan)
    db_session.flush()
    org.subscription_plan_id = free_plan.id
    db_session.commit()

    db_session.add(CampaignWhitelist(organization_id=org.id, meta_campaign_id=campaign.id, added_by_user_id=user.id))
    db_session.add(CampaignAutonomySettings(meta_campaign_id=campaign.id, autonomy_level=AutonomyLevel.AUTONOMOUS, auto_executable_action_types=["pause_ad"], max_automated_actions_per_day=100, max_daily_spend_cents=100000, max_budget_increase_percent=100))
    db_session.add(AdAccountSpendLimit(meta_ad_account_id=ad_account.id, daily_spend_limit_cents=100000))
    db_session.commit()

    decision = OptimizationDecision(organization_id=org.id, meta_campaign_id=campaign.id, observation="x", evidence_json={}, action_type=OptimizationActionType.PAUSE_AD, proposed_action="x", action_payload={}, expected_outcome="x", confidence=0.7, risk=DecisionRisk.LOW, required_permission="can_manage_campaigns", status=DecisionStatus.RECOMMENDED)
    db_session.add(decision)
    db_session.commit()

    with pytest.raises(execution.AutonomousExecutionBlockedError):
        execution.process_decision_autonomous(db_session, organization_id=org.id, decision=decision)

    db_session.refresh(decision)
    assert decision.status != DecisionStatus.AUTO_APPROVED
