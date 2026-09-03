"""
Meta Ads endpoints.

Note: OAuth connect/callback for meta_ads reuses the EXISTING generic
/oauth/{platform_type}/connect flow - meta_ads was registered in
app.oauth.registry, and that flow is genuinely platform-agnostic, so no
new OAuth endpoint code is needed here. This module covers everything
Meta-Ads-specific: ad accounts, spend limits, campaigns, the approval
flow, and insights.

Permission gating: reading is gated at plain org membership; connecting
an ad account and setting spend limits/emergency stop use
can_manage_integrations; requesting/reviewing/executing campaign
actions use can_manage_campaigns.
"""
import uuid
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import app.meta_ads.execution_service as execution_service
import app.meta_ads.spend_guard as spend_guard
from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.ad_account_spend_limit import AdAccountSpendLimit
from app.models.approval_request import ApprovalRequest
from app.models.connected_account import ConnectedAccount
from app.models.meta_ad_account import MetaAdAccount
from app.models.meta_campaign import MetaCampaign
from app.models.meta_insight_snapshot import MetaInsightEntityType, MetaInsightSnapshot
from app.models.organization import OrganizationMember
from app.schemas.meta_ads import (
    AdAccountSpendLimitPublic,
    ApprovalRequestPublic,
    ConnectMetaAdAccountRequest,
    MetaAdAccountPublic,
    MetaCampaignPublic,
    MetaInsightSnapshotPublic,
    RequestBudgetChangeRequest,
    RequestStatusChangeRequest,
    ReviewApprovalRequest,
    SetEmergencyStopRequest,
    SetSpendLimitRequest,
)

router = APIRouter(prefix="/meta-ads", tags=["meta-ads"])


@router.get("/ad-accounts", response_model=list[MetaAdAccountPublic])
def list_ad_accounts(member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return db.query(MetaAdAccount).filter(MetaAdAccount.organization_id == member.organization_id).all()


@router.post("/ad-accounts", response_model=MetaAdAccountPublic, status_code=status.HTTP_201_CREATED)
def connect_ad_account(
    payload: ConnectMetaAdAccountRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    connected = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.id == payload.connected_account_id,
            ConnectedAccount.organization_id == member.organization_id,
        )
        .first()
    )
    if not connected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connected account not found")

    ad_account = MetaAdAccount(
        organization_id=member.organization_id,
        connected_account_id=payload.connected_account_id,
        external_ad_account_id=payload.external_ad_account_id,
        name=payload.name,
        currency=payload.currency,
        timezone_name=payload.timezone_name,
    )
    db.add(ad_account)
    db.commit()
    db.refresh(ad_account)
    return ad_account


@router.get("/ad-accounts/{ad_account_id}/spend-limit", response_model=Optional[AdAccountSpendLimitPublic])
def get_spend_limit(
    ad_account_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return db.query(AdAccountSpendLimit).filter(AdAccountSpendLimit.meta_ad_account_id == ad_account_id).first()


@router.put("/ad-accounts/{ad_account_id}/spend-limit", response_model=AdAccountSpendLimitPublic)
def set_spend_limit(
    ad_account_id: uuid.UUID,
    payload: SetSpendLimitRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    ad_account = db.get(MetaAdAccount, ad_account_id)
    if not ad_account or ad_account.organization_id != member.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")

    limit = db.query(AdAccountSpendLimit).filter(AdAccountSpendLimit.meta_ad_account_id == ad_account_id).first()
    if limit:
        limit.daily_spend_limit_cents = payload.daily_spend_limit_cents
    else:
        limit = AdAccountSpendLimit(
            meta_ad_account_id=ad_account_id, daily_spend_limit_cents=payload.daily_spend_limit_cents
        )
        db.add(limit)
    db.commit()
    db.refresh(limit)
    return limit


@router.post("/ad-accounts/{ad_account_id}/emergency-stop", response_model=AdAccountSpendLimitPublic)
def set_emergency_stop(
    ad_account_id: uuid.UUID,
    payload: SetEmergencyStopRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    limit = db.query(AdAccountSpendLimit).filter(AdAccountSpendLimit.meta_ad_account_id == ad_account_id).first()
    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No spend limit configured for this ad account yet"
        )

    limit.is_emergency_stopped = payload.stopped
    if payload.stopped:
        limit.emergency_stopped_at = datetime.now(timezone.utc)
        limit.emergency_stopped_by_user_id = member.user_id
        limit.emergency_stop_reason = payload.reason
    else:
        limit.emergency_stopped_at = None
        limit.emergency_stopped_by_user_id = None
        limit.emergency_stop_reason = None
    db.commit()
    db.refresh(limit)
    return limit


@router.get("/meta-campaigns", response_model=list[MetaCampaignPublic])
def list_meta_campaigns(member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return db.query(MetaCampaign).filter(MetaCampaign.organization_id == member.organization_id).all()


@router.get("/meta-campaigns/{meta_campaign_id}/insights", response_model=list[MetaInsightSnapshotPublic])
def get_campaign_insights(
    meta_campaign_id: uuid.UUID,
    date_start: Optional[date_type] = Query(default=None),
    date_stop: Optional[date_type] = Query(default=None),
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    campaign = db.get(MetaCampaign, meta_campaign_id)
    if not campaign or campaign.organization_id != member.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meta campaign not found")

    query = db.query(MetaInsightSnapshot).filter(
        MetaInsightSnapshot.entity_type == MetaInsightEntityType.CAMPAIGN,
        MetaInsightSnapshot.entity_id == meta_campaign_id,
    )
    if date_start:
        query = query.filter(MetaInsightSnapshot.date >= date_start)
    if date_stop:
        query = query.filter(MetaInsightSnapshot.date <= date_stop)
    return query.order_by(MetaInsightSnapshot.date).all()


@router.post("/meta-campaigns/{meta_campaign_id}/request-status-change", response_model=ApprovalRequestPublic)
def request_status_change(
    meta_campaign_id: uuid.UUID,
    payload: RequestStatusChangeRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return execution_service.request_campaign_status_change(
            db,
            organization_id=member.organization_id,
            requested_by_user_id=member.user_id,
            meta_campaign_id=meta_campaign_id,
            new_status=payload.new_status,
        )
    except execution_service.ExecutionServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/meta-campaigns/{meta_campaign_id}/request-budget-change", response_model=ApprovalRequestPublic)
def request_budget_change(
    meta_campaign_id: uuid.UUID,
    payload: RequestBudgetChangeRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return execution_service.request_budget_change(
            db,
            organization_id=member.organization_id,
            requested_by_user_id=member.user_id,
            meta_campaign_id=meta_campaign_id,
            new_daily_budget_cents=payload.new_daily_budget_cents,
        )
    except execution_service.ExecutionServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/approval-requests", response_model=list[ApprovalRequestPublic])
def list_approval_requests(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    query = db.query(ApprovalRequest).filter(ApprovalRequest.organization_id == member.organization_id)
    if status_filter:
        query = query.filter(ApprovalRequest.status == status_filter)
    return query.order_by(ApprovalRequest.created_at.desc()).all()


@router.post("/approval-requests/{approval_request_id}/review", response_model=ApprovalRequestPublic)
def review(
    approval_request_id: uuid.UUID,
    payload: ReviewApprovalRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return execution_service.review_approval(
            db,
            organization_id=member.organization_id,
            reviewed_by_user_id=member.user_id,
            approval_request_id=approval_request_id,
            approve=payload.approve,
            review_notes=payload.review_notes,
        )
    except execution_service.ExecutionServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/approval-requests/{approval_request_id}/execute", response_model=MetaCampaignPublic)
def execute(
    approval_request_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    approval = db.get(ApprovalRequest, approval_request_id)
    if not approval or approval.organization_id != member.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    try:
        if approval.action_type.value in ("campaign_pause", "campaign_launch"):
            return execution_service.execute_campaign_status_change(
                db,
                organization_id=member.organization_id,
                executed_by_user_id=member.user_id,
                approval_request_id=approval_request_id,
            )
        if approval.action_type.value == "campaign_budget_change":
            return execution_service.execute_budget_change(
                db,
                organization_id=member.organization_id,
                executed_by_user_id=member.user_id,
                approval_request_id=approval_request_id,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No execution path for action type {approval.action_type.value}",
        )
    except execution_service.ExecutionServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (
        spend_guard.SpendLimitExceededError,
        spend_guard.EmergencyStopActiveError,
        spend_guard.SpendLimitMissingError,
    ) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
