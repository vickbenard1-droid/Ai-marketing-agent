"""Optimization agent management service - autonomy settings/whitelist CRUD, decision review."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

import app.optimization.execution as execution
from app.audit.service import write_audit_log
from app.models.campaign_autonomy_settings import AutonomyLevel, CampaignAutonomySettings, CampaignWhitelist
from app.models.meta_campaign import MetaCampaign
from app.models.optimization_decision import DecisionStatus, OptimizationActionType, OptimizationDecision


class OptimizationManagementError(Exception):
    pass


def get_or_create_autonomy_settings(db: Session, meta_campaign_id: uuid.UUID) -> CampaignAutonomySettings:
    settings = db.query(CampaignAutonomySettings).filter(CampaignAutonomySettings.meta_campaign_id == meta_campaign_id).first()
    if settings:
        return settings
    settings = CampaignAutonomySettings(meta_campaign_id=meta_campaign_id, autonomy_level=AutonomyLevel.MANUAL)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def set_autonomy_settings(db: Session, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, meta_campaign_id: uuid.UUID, autonomy_level: AutonomyLevel, max_daily_spend_cents: Optional[int], max_budget_increase_percent: Optional[int], max_automated_actions_per_day: Optional[int], auto_executable_action_types: list) -> CampaignAutonomySettings:
    campaign = db.query(MetaCampaign).filter(MetaCampaign.id == meta_campaign_id, MetaCampaign.organization_id == organization_id).first()
    if not campaign:
        raise OptimizationManagementError("Meta campaign not found")
    for action_type_str in auto_executable_action_types:
        try:
            OptimizationActionType(action_type_str)
        except ValueError:
            raise OptimizationManagementError(f"'{action_type_str}' is not a valid optimization action type")

    settings = get_or_create_autonomy_settings(db, meta_campaign_id)
    settings.autonomy_level = autonomy_level
    settings.max_daily_spend_cents = max_daily_spend_cents
    settings.max_budget_increase_percent = max_budget_increase_percent
    settings.max_automated_actions_per_day = max_automated_actions_per_day
    settings.auto_executable_action_types = auto_executable_action_types
    write_audit_log(db, organization_id=organization_id, actor_user_id=actor_user_id, action="optimization.autonomy_settings_updated", resource_type="CampaignAutonomySettings", resource_id=str(settings.id), metadata={"autonomy_level": autonomy_level.value})
    db.commit()
    db.refresh(settings)
    return settings


def set_emergency_stop(db: Session, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, meta_campaign_id: uuid.UUID, stopped: bool, reason: Optional[str]) -> CampaignAutonomySettings:
    settings = get_or_create_autonomy_settings(db, meta_campaign_id)
    settings.is_emergency_stopped = stopped
    if stopped:
        settings.emergency_stopped_at = datetime.now(timezone.utc)
        settings.emergency_stopped_by_user_id = actor_user_id
        settings.emergency_stop_reason = reason
    else:
        settings.emergency_stopped_at = None
        settings.emergency_stopped_by_user_id = None
        settings.emergency_stop_reason = None
    write_audit_log(db, organization_id=organization_id, actor_user_id=actor_user_id, action="optimization.emergency_stop_enabled" if stopped else "optimization.emergency_stop_disabled", resource_type="CampaignAutonomySettings", resource_id=str(settings.id))
    db.commit()
    db.refresh(settings)
    return settings


def add_to_whitelist(db: Session, *, organization_id: uuid.UUID, added_by_user_id: uuid.UUID, meta_campaign_id: uuid.UUID) -> CampaignWhitelist:
    campaign = db.query(MetaCampaign).filter(MetaCampaign.id == meta_campaign_id, MetaCampaign.organization_id == organization_id).first()
    if not campaign:
        raise OptimizationManagementError("Meta campaign not found")
    existing = db.query(CampaignWhitelist).filter(CampaignWhitelist.meta_campaign_id == meta_campaign_id).first()
    if existing:
        raise OptimizationManagementError("This campaign is already whitelisted")
    entry = CampaignWhitelist(organization_id=organization_id, meta_campaign_id=meta_campaign_id, added_by_user_id=added_by_user_id)
    db.add(entry)
    write_audit_log(db, organization_id=organization_id, actor_user_id=added_by_user_id, action="optimization.campaign_whitelisted", resource_type="MetaCampaign", resource_id=str(meta_campaign_id))
    db.commit()
    db.refresh(entry)
    return entry


def remove_from_whitelist(db: Session, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, meta_campaign_id: uuid.UUID) -> None:
    entry = db.query(CampaignWhitelist).filter(CampaignWhitelist.organization_id == organization_id, CampaignWhitelist.meta_campaign_id == meta_campaign_id).first()
    if not entry:
        raise OptimizationManagementError("This campaign is not on the whitelist")
    db.delete(entry)
    write_audit_log(db, organization_id=organization_id, actor_user_id=actor_user_id, action="optimization.campaign_removed_from_whitelist", resource_type="MetaCampaign", resource_id=str(meta_campaign_id))
    db.commit()


def review_decision(db: Session, *, organization_id: uuid.UUID, reviewed_by_user_id: uuid.UUID, decision: OptimizationDecision, approve: bool, new_daily_budget_cents: Optional[int] = None) -> OptimizationDecision:
    if decision.status != DecisionStatus.RECOMMENDED:
        raise OptimizationManagementError(f"Only a RECOMMENDED decision can be reviewed (current: {decision.status.value})")
    decision.reviewed_by_user_id = reviewed_by_user_id
    decision.reviewed_at = datetime.now(timezone.utc)
    if not approve:
        decision.status = DecisionStatus.REJECTED
        db.commit()
        db.refresh(decision)
        return decision
    if decision.action_type in (OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.INCREASE_BUDGET):
        if new_daily_budget_cents is None:
            raise OptimizationManagementError("new_daily_budget_cents is required when approving a budget-changing decision")
        decision.action_payload = {"new_daily_budget_cents": new_daily_budget_cents}
    decision.status = DecisionStatus.APPROVED
    db.commit()
    return execution.process_decision_assisted(db, organization_id=organization_id, requested_by_user_id=reviewed_by_user_id, decision=decision)
