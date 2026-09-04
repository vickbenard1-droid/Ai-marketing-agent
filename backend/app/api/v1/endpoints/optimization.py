"""Optimization agent endpoints."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import app.optimization.execution as execution
import app.optimization.orchestrator as orchestrator
import app.optimization.service as opt_service
from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.meta_campaign import MetaCampaign
from app.models.optimization_decision import OptimizationDecision
from app.models.organization import OrganizationMember
from app.schemas.optimization import (
    AutonomySettingsPublic,
    OptimizationDecisionPublic,
    ReviewDecisionRequest,
    ScanCampaignResponse,
    SetAutonomySettingsRequest,
    SetEmergencyStopRequest,
    WhitelistEntryPublic,
)

router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.get("/meta-campaigns/{meta_campaign_id}/autonomy-settings", response_model=AutonomySettingsPublic)
def get_autonomy_settings(meta_campaign_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    campaign = db.query(MetaCampaign).filter(MetaCampaign.id == meta_campaign_id, MetaCampaign.organization_id == member.organization_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meta campaign not found")
    return opt_service.get_or_create_autonomy_settings(db, meta_campaign_id)


@router.put("/meta-campaigns/{meta_campaign_id}/autonomy-settings", response_model=AutonomySettingsPublic)
def put_autonomy_settings(meta_campaign_id: uuid.UUID, payload: SetAutonomySettingsRequest, member: OrganizationMember = Depends(require_permission("can_manage_integrations")), db: Session = Depends(get_db)):
    try:
        return opt_service.set_autonomy_settings(db, organization_id=member.organization_id, actor_user_id=member.user_id, meta_campaign_id=meta_campaign_id, autonomy_level=payload.autonomy_level, max_daily_spend_cents=payload.max_daily_spend_cents, max_budget_increase_percent=payload.max_budget_increase_percent, max_automated_actions_per_day=payload.max_automated_actions_per_day, auto_executable_action_types=payload.auto_executable_action_types)
    except opt_service.OptimizationManagementError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/meta-campaigns/{meta_campaign_id}/emergency-stop", response_model=AutonomySettingsPublic)
def post_emergency_stop(meta_campaign_id: uuid.UUID, payload: SetEmergencyStopRequest, member: OrganizationMember = Depends(require_permission("can_manage_integrations")), db: Session = Depends(get_db)):
    return opt_service.set_emergency_stop(db, organization_id=member.organization_id, actor_user_id=member.user_id, meta_campaign_id=meta_campaign_id, stopped=payload.stopped, reason=payload.reason)


@router.get("/meta-campaigns/{meta_campaign_id}/whitelist", response_model=Optional[WhitelistEntryPublic])
def get_whitelist_status(meta_campaign_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    from app.models.campaign_autonomy_settings import CampaignWhitelist
    return db.query(CampaignWhitelist).filter(CampaignWhitelist.organization_id == member.organization_id, CampaignWhitelist.meta_campaign_id == meta_campaign_id).first()


@router.post("/meta-campaigns/{meta_campaign_id}/whitelist", response_model=WhitelistEntryPublic, status_code=status.HTTP_201_CREATED)
def post_whitelist(meta_campaign_id: uuid.UUID, member: OrganizationMember = Depends(require_permission("can_manage_integrations")), db: Session = Depends(get_db)):
    try:
        return opt_service.add_to_whitelist(db, organization_id=member.organization_id, added_by_user_id=member.user_id, meta_campaign_id=meta_campaign_id)
    except opt_service.OptimizationManagementError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/meta-campaigns/{meta_campaign_id}/whitelist", status_code=status.HTTP_204_NO_CONTENT)
def delete_whitelist(meta_campaign_id: uuid.UUID, member: OrganizationMember = Depends(require_permission("can_manage_integrations")), db: Session = Depends(get_db)):
    try:
        opt_service.remove_from_whitelist(db, organization_id=member.organization_id, actor_user_id=member.user_id, meta_campaign_id=meta_campaign_id)
    except opt_service.OptimizationManagementError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/decisions", response_model=list[OptimizationDecisionPublic])
def list_decisions(meta_campaign_id: Optional[uuid.UUID] = Query(default=None), status_filter: Optional[str] = Query(default=None, alias="status"), member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    query = db.query(OptimizationDecision).filter(OptimizationDecision.organization_id == member.organization_id)
    if meta_campaign_id:
        query = query.filter(OptimizationDecision.meta_campaign_id == meta_campaign_id)
    if status_filter:
        query = query.filter(OptimizationDecision.status == status_filter)
    return query.order_by(OptimizationDecision.created_at.desc()).all()


@router.post("/decisions/{decision_id}/review", response_model=OptimizationDecisionPublic)
def review_decision(decision_id: uuid.UUID, payload: ReviewDecisionRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    decision = db.query(OptimizationDecision).filter(OptimizationDecision.id == decision_id, OptimizationDecision.organization_id == member.organization_id).first()
    if not decision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    try:
        return opt_service.review_decision(db, organization_id=member.organization_id, reviewed_by_user_id=member.user_id, decision=decision, approve=payload.approve, new_daily_budget_cents=payload.new_daily_budget_cents)
    except (opt_service.OptimizationManagementError, execution.ExecutionFrameworkError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/meta-campaigns/{meta_campaign_id}/scan", response_model=ScanCampaignResponse)
def scan_campaign(meta_campaign_id: uuid.UUID, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    campaign = db.query(MetaCampaign).filter(MetaCampaign.id == meta_campaign_id, MetaCampaign.organization_id == member.organization_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meta campaign not found")
    if not campaign.external_campaign_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This campaign has not been created in Meta yet")
    result = orchestrator.scan_campaign(db, organization_id=member.organization_id, meta_campaign=campaign, requested_by_user_id=member.user_id)
    return ScanCampaignResponse(meta_campaign_id=result.meta_campaign_id, decisions_created=[str(d.id) for d in result.decisions_created], errors=result.errors)
