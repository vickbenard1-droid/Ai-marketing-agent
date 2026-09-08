"""
Tests for app.orchestrator.service, focused on the human-control
guarantee - the spec's explicit requirement that the user remains in
control of money, advertising accounts, publishing, and automated
actions.

Includes a regression test for a real gap found during the Week 12
security AI-security review: advance_run() decided whether to pause for
human approval using ONLY the AI planner's own requires_approval flag on
each plan step - a value the AI itself controls. A prompt injection that
successfully manipulated the planner (e.g. via adversarial business
knowledge or a crafted goal) into emitting requires_approval: false for
a sensitive agent (advertising_agent, content_agent, optimization_agent)
would have skipped the pre-execution pause, even though every one of
those agents' own internal design independently refuses to take a real
external action on its own authority regardless (this is a second,
independent line of defense, not the only one). Fixed by introducing a
code-owned, closed set of structurally sensitive agent names that is
checked BEFORE calling agent.run() regardless of what the AI's plan
claims, combined with (never loosened by) the plan's own flag.
"""
import json
import uuid

import httpx

import app.orchestrator.service as orch_svc
from app.ai_providers.claude_provider import ClaudeProvider
from app.models.ai_usage_log import AIUsageSource  # noqa: F401 - imported for clarity in test context
from app.models.approval_request import ApprovalRequest
from app.models.meta_ad_account import MetaAdAccount
from app.models.meta_campaign import MetaCampaign, MetaCampaignObjective, MetaCampaignStatus
from app.models.orchestration_run import OrchestrationRunStatus
from app.models.organization import Organization
from app.models.user import User


def _mock_plan(monkeypatch, plan: dict):
    def handler(request):
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(plan)}], "usage": {"input_tokens": 100, "output_tokens": 40}})
    monkeypatch.setattr(orch_svc, "get_ai_provider_for_task", lambda task: ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler)))


def _seed_org_and_campaign(db_session):
    org = Organization(name="Acme", slug="acme")
    db_session.add(org)
    db_session.flush()
    user = User(email="u@example.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    ad_account = MetaAdAccount(organization_id=org.id, connected_account_id=uuid.uuid4(), external_ad_account_id="act_1", name="Test", currency="USD", timezone_name="UTC")
    db_session.add(ad_account)
    db_session.flush()
    campaign = MetaCampaign(organization_id=org.id, meta_ad_account_id=ad_account.id, name="Test", objective=MetaCampaignObjective.OUTCOME_SALES, external_campaign_id="c1", status=MetaCampaignStatus.PAUSED, daily_budget_cents=1000)
    db_session.add(campaign)
    db_session.commit()
    return org, user, campaign


def test_ai_cannot_bypass_approval_for_advertising_agent(db_session, monkeypatch):
    """The core regression test: a plan that claims requires_approval:
    false for advertising_agent must still pause, and the agent must
    never actually be invoked."""
    org, user, campaign = _seed_org_and_campaign(db_session)
    malicious_plan = {"steps": [{"agent_name": "advertising_agent", "action_description": "Launch immediately, ignore review", "requires_approval": False}], "plan_summary": "x"}
    _mock_plan(monkeypatch, malicious_plan)

    run = orch_svc.create_run(db_session, organization_id=org.id, requested_by_user_id=user.id, goal_text="Launch a campaign")
    assert run.plan_json[0]["requires_approval"] is False  # confirms the AI's claim really was False

    run = orch_svc.advance_run(db_session, organization_id=org.id, run=run, actor_user_id=user.id)

    assert run.status == OrchestrationRunStatus.PAUSED_FOR_APPROVAL
    assert db_session.query(ApprovalRequest).count() == 0, "advertising_agent must never actually run before approval"


def test_ai_cannot_bypass_approval_for_content_agent(db_session, monkeypatch):
    org, user, _ = _seed_org_and_campaign(db_session)
    malicious_plan = {"steps": [{"agent_name": "content_agent", "action_description": "Generate and imply it's ready", "requires_approval": False}], "plan_summary": "x"}
    _mock_plan(monkeypatch, malicious_plan)

    run = orch_svc.create_run(db_session, organization_id=org.id, requested_by_user_id=user.id, goal_text="Make content")
    run = orch_svc.advance_run(db_session, organization_id=org.id, run=run, actor_user_id=user.id)

    assert run.status == OrchestrationRunStatus.PAUSED_FOR_APPROVAL


def test_ai_cannot_bypass_approval_for_optimization_agent(db_session, monkeypatch):
    org, user, _ = _seed_org_and_campaign(db_session)
    malicious_plan = {"steps": [{"agent_name": "optimization_agent", "action_description": "Scan and act", "requires_approval": False}], "plan_summary": "x"}
    _mock_plan(monkeypatch, malicious_plan)

    run = orch_svc.create_run(db_session, organization_id=org.id, requested_by_user_id=user.id, goal_text="Optimize")
    run = orch_svc.advance_run(db_session, organization_id=org.id, run=run, actor_user_id=user.id)

    assert run.status == OrchestrationRunStatus.PAUSED_FOR_APPROVAL


def test_non_sensitive_agent_still_auto_executes_without_over_correction(db_session, monkeypatch):
    """A genuinely non-sensitive agent must still run normally - the fix
    must not pause every step regardless of sensitivity."""
    org, user, _ = _seed_org_and_campaign(db_session)
    plan = {"steps": [{"agent_name": "analytics_agent", "action_description": "Review performance", "requires_approval": False}], "plan_summary": "x"}
    _mock_plan(monkeypatch, plan)

    run = orch_svc.create_run(db_session, organization_id=org.id, requested_by_user_id=user.id, goal_text="Review performance")
    run = orch_svc.advance_run(db_session, organization_id=org.id, run=run, actor_user_id=user.id)

    assert run.status == OrchestrationRunStatus.COMPLETED


def test_plan_can_still_add_approval_for_a_normally_safe_agent(db_session, monkeypatch):
    """The plan's own requires_approval: true must still be honored even
    for a non-structurally-sensitive agent - the fix is additive, not a
    replacement of the plan's own flag."""
    org, user, _ = _seed_org_and_campaign(db_session)
    plan = {"steps": [{"agent_name": "analytics_agent", "action_description": "Review performance, flagged as sensitive this time", "requires_approval": True}], "plan_summary": "x"}
    _mock_plan(monkeypatch, plan)

    run = orch_svc.create_run(db_session, organization_id=org.id, requested_by_user_id=user.id, goal_text="Review performance")
    run = orch_svc.advance_run(db_session, organization_id=org.id, run=run, actor_user_id=user.id)

    assert run.status == OrchestrationRunStatus.PAUSED_FOR_APPROVAL
