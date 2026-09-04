"""
Execution framework.

Routes an OptimizationDecision through Manual/Assisted/Autonomous per
this campaign's CampaignAutonomySettings.autonomy_level (one blanket
mode per campaign):

- MANUAL: no-op beyond what decision_engine.py already did.
- ASSISTED: creates a real Week 7 ApprovalRequest via the SAME
  request_*/execute_* functions Week 7's own UI uses. A person must
  still explicitly approve.
- AUTONOMOUS: safety.assert_can_execute_autonomously() FIRST - if that
  raises, execution stops immediately. Only if it passes does this
  create+approve+execute an ApprovalRequest in one flow, still through
  the exact same Week 7 functions.

Only PAUSE_AD and REDUCE_BUDGET/INCREASE_BUDGET have real execution
paths - the rest (new creative, headline/CTA changes, retargeting,
structural changes) would need real Meta Ad Creative API work beyond
this week's scope; attempting to execute one raises NotYetExecutableError
rather than silently no-op or fake success.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

import app.meta_ads.execution_service as meta_execution
import app.optimization.safety as safety
from app.audit.service import write_audit_log
from app.models.automated_action_log import AutomatedActionLog
from app.models.campaign_autonomy_settings import AutonomyLevel, CampaignAutonomySettings
from app.models.optimization_decision import DecisionStatus, OptimizationActionType, OptimizationDecision


class ExecutionFrameworkError(Exception):
    pass


class NotYetExecutableError(ExecutionFrameworkError):
    pass


class AutonomousExecutionBlockedError(ExecutionFrameworkError):
    pass


def _get_autonomy_level(db: Session, meta_campaign_id: uuid.UUID) -> AutonomyLevel:
    settings = db.query(CampaignAutonomySettings).filter(CampaignAutonomySettings.meta_campaign_id == meta_campaign_id).first()
    return settings.autonomy_level if settings else AutonomyLevel.MANUAL


def _create_approval_request(db: Session, *, organization_id: uuid.UUID, requested_by_user_id: Optional[uuid.UUID], decision: OptimizationDecision):
    if decision.action_type == OptimizationActionType.PAUSE_AD:
        return meta_execution.request_campaign_status_change(
            db, organization_id=organization_id, requested_by_user_id=requested_by_user_id, meta_campaign_id=decision.meta_campaign_id, new_status="PAUSED"
        )
    if decision.action_type in (OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.INCREASE_BUDGET):
        new_budget = decision.action_payload.get("new_daily_budget_cents")
        if new_budget is None:
            raise ExecutionFrameworkError("action_payload is missing new_daily_budget_cents")
        return meta_execution.request_budget_change(
            db, organization_id=organization_id, requested_by_user_id=requested_by_user_id, meta_campaign_id=decision.meta_campaign_id, new_daily_budget_cents=new_budget
        )
    raise NotYetExecutableError(f"Action type {decision.action_type.value} has no execution path yet")


def _execute_approval_request(db: Session, *, organization_id: uuid.UUID, executed_by_user_id: Optional[uuid.UUID], decision: OptimizationDecision):
    if decision.action_type == OptimizationActionType.PAUSE_AD:
        return meta_execution.execute_campaign_status_change(db, organization_id=organization_id, executed_by_user_id=executed_by_user_id, approval_request_id=decision.resulting_approval_request_id)
    if decision.action_type in (OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.INCREASE_BUDGET):
        return meta_execution.execute_budget_change(db, organization_id=organization_id, executed_by_user_id=executed_by_user_id, approval_request_id=decision.resulting_approval_request_id)
    raise NotYetExecutableError(f"Action type {decision.action_type.value} has no execution path yet")


def process_decision_manual(db: Session, decision: OptimizationDecision) -> OptimizationDecision:
    return decision


def process_decision_assisted(db: Session, *, organization_id: uuid.UUID, requested_by_user_id: Optional[uuid.UUID], decision: OptimizationDecision) -> OptimizationDecision:
    approval_request = _create_approval_request(db, organization_id=organization_id, requested_by_user_id=requested_by_user_id, decision=decision)
    decision.resulting_approval_request_id = approval_request.id
    db.commit()
    db.refresh(decision)
    return decision


def process_decision_autonomous(db: Session, *, organization_id: uuid.UUID, decision: OptimizationDecision) -> OptimizationDecision:
    proposed_budget = None
    if decision.action_type in (OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.INCREASE_BUDGET):
        proposed_budget = decision.action_payload.get("new_daily_budget_cents")

    try:
        safety.assert_can_execute_autonomously(
            db, organization_id=organization_id, meta_campaign_id=decision.meta_campaign_id, action_type=decision.action_type, proposed_daily_budget_cents=proposed_budget
        )
    except (
        safety.NotWhitelistedError, safety.AutonomyEmergencyStopActiveError, safety.AutonomySettingsMissingError,
        safety.AutonomyLevelInsufficientError, safety.DailyActionLimitExceededError,
        safety.BudgetIncreaseLimitExceededError, safety.DailySpendLimitExceededError,
    ) as exc:
        raise AutonomousExecutionBlockedError(str(exc)) from exc

    approval_request = _create_approval_request(db, organization_id=organization_id, requested_by_user_id=None, decision=decision)
    decision.resulting_approval_request_id = approval_request.id
    decision.status = DecisionStatus.AUTO_APPROVED
    db.commit()

    meta_execution.review_approval(
        db, organization_id=organization_id, reviewed_by_user_id=None, approval_request_id=approval_request.id, approve=True,
        review_notes="Auto-approved by the optimization agent under AUTONOMOUS mode.",
    )

    try:
        _execute_approval_request(db, organization_id=organization_id, executed_by_user_id=None, decision=decision)
    except Exception as exc:
        decision.status = DecisionStatus.EXECUTION_FAILED
        db.commit()
        raise ExecutionFrameworkError(f"Autonomous execution failed: {exc}") from exc

    decision.status = DecisionStatus.EXECUTED
    db.add(AutomatedActionLog(organization_id=organization_id, meta_campaign_id=decision.meta_campaign_id, optimization_decision_id=decision.id, executed_via="autonomous", executed_at=datetime.now(timezone.utc)))
    write_audit_log(
        db, organization_id=organization_id, actor_user_id=None, action="optimization_decision.autonomous_execution",
        resource_type="OptimizationDecision", resource_id=str(decision.id),
        metadata={"action_type": decision.action_type.value, "confidence": decision.confidence, "risk": decision.risk.value},
    )
    db.commit()
    db.refresh(decision)
    return decision


def process_decision(db: Session, *, organization_id: uuid.UUID, requested_by_user_id: Optional[uuid.UUID], decision: OptimizationDecision) -> OptimizationDecision:
    level = _get_autonomy_level(db, decision.meta_campaign_id)
    if level == AutonomyLevel.MANUAL:
        return process_decision_manual(db, decision)
    if level == AutonomyLevel.ASSISTED:
        return process_decision_assisted(db, organization_id=organization_id, requested_by_user_id=requested_by_user_id, decision=decision)
    return process_decision_autonomous(db, organization_id=organization_id, decision=decision)
