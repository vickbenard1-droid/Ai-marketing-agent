"""
Meta Ads execution service.

Ties together ApprovalRequest (the request/approve/execute substrate,
already existing from Week 3), app.meta_ads.spend_guard (the fail-closed
safety gate), and app.meta_ads.meta_client (the real Meta API calls).

Flow for every spend-affecting action:
1. request_*() creates a PENDING ApprovalRequest - no Meta API call yet.
2. review_approval() lets a person approve or reject - still no Meta
   API call on approval itself, only a status change.
3. execute_*() is a SEPARATE step: calls spend_guard.assert_within_limits()
   FIRST (if this is a budget-affecting action), and only if that
   passes does it call the real Meta API and write an audit log entry.

Keeping approve and execute as two distinct steps means a person
approving an action today isn't silently executing it against whatever
the account's spend situation happens to be at that later moment
without a final check - the guard is evaluated at EXECUTION time, not
at approval time.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

import app.meta_ads.spend_guard as spend_guard
from app.audit.service import write_audit_log
from app.meta_ads.meta_client import MetaMarketingClient
from app.models.approval_request import ApprovalActionType, ApprovalRequest, ApprovalStatus
from app.models.meta_ad_account import MetaAdAccount
from app.models.meta_campaign import MetaCampaign, MetaCampaignStatus
from app.oauth.service import decrypt_credentials_for_publishing


class ExecutionServiceError(Exception):
    """Raised for execution-flow failures the API layer should turn into 4xx responses."""


def request_campaign_status_change(
    db: Session,
    *,
    organization_id: uuid.UUID,
    requested_by_user_id: Optional[uuid.UUID],
    meta_campaign_id: uuid.UUID,
    new_status: str,
) -> ApprovalRequest:
    campaign = db.get(MetaCampaign, meta_campaign_id)
    if not campaign or campaign.organization_id != organization_id:
        raise ExecutionServiceError("Meta campaign not found")

    approval = ApprovalRequest(
        organization_id=organization_id,
        action_type=(
            ApprovalActionType.CAMPAIGN_PAUSE if new_status == "PAUSED" else ApprovalActionType.CAMPAIGN_LAUNCH
        ),
        title=f"Change '{campaign.name}' status to {new_status}",
        action_payload={"meta_campaign_id": str(meta_campaign_id), "new_status": new_status},
        requested_by_user_id=requested_by_user_id,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def request_budget_change(
    db: Session,
    *,
    organization_id: uuid.UUID,
    requested_by_user_id: Optional[uuid.UUID],
    meta_campaign_id: uuid.UUID,
    new_daily_budget_cents: int,
) -> ApprovalRequest:
    campaign = db.get(MetaCampaign, meta_campaign_id)
    if not campaign or campaign.organization_id != organization_id:
        raise ExecutionServiceError("Meta campaign not found")

    approval = ApprovalRequest(
        organization_id=organization_id,
        action_type=ApprovalActionType.CAMPAIGN_BUDGET_CHANGE,
        title=f"Change '{campaign.name}' daily budget to {new_daily_budget_cents} cents",
        action_payload={"meta_campaign_id": str(meta_campaign_id), "new_daily_budget_cents": new_daily_budget_cents},
        requested_by_user_id=requested_by_user_id,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def review_approval(
    db: Session,
    *,
    organization_id: uuid.UUID,
    reviewed_by_user_id: Optional[uuid.UUID],
    approval_request_id: uuid.UUID,
    approve: bool,
    review_notes: Optional[str] = None,
) -> ApprovalRequest:
    approval = db.get(ApprovalRequest, approval_request_id)
    if not approval or approval.organization_id != organization_id:
        raise ExecutionServiceError("Approval request not found")
    if approval.status != ApprovalStatus.PENDING:
        raise ExecutionServiceError(
            f"Only a PENDING request can be reviewed (current status: {approval.status.value})"
        )

    approval.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
    approval.reviewed_by_user_id = reviewed_by_user_id
    approval.reviewed_at = datetime.now(timezone.utc)
    approval.review_notes = review_notes
    db.commit()
    db.refresh(approval)
    return approval


def _get_client_for_campaign(db: Session, campaign: MetaCampaign) -> MetaMarketingClient:
    ad_account = db.get(MetaAdAccount, campaign.meta_ad_account_id)
    credentials = decrypt_credentials_for_publishing(ad_account.connected_account)
    if not credentials:
        raise ExecutionServiceError("No usable Meta Ads credentials — reauthorize the connection")
    return MetaMarketingClient(credentials["access_token"])


def execute_campaign_status_change(
    db: Session,
    *,
    organization_id: uuid.UUID,
    executed_by_user_id: Optional[uuid.UUID],
    approval_request_id: uuid.UUID,
) -> MetaCampaign:
    approval = db.get(ApprovalRequest, approval_request_id)
    if not approval or approval.organization_id != organization_id:
        raise ExecutionServiceError("Approval request not found")
    if approval.status != ApprovalStatus.APPROVED:
        raise ExecutionServiceError(
            f"Only an APPROVED request can be executed (current status: {approval.status.value})"
        )

    campaign = db.get(MetaCampaign, uuid.UUID(approval.action_payload["meta_campaign_id"]))
    new_status = approval.action_payload["new_status"]

    if new_status == "ACTIVE":
        spend_guard.assert_within_limits(
            db,
            meta_ad_account_id=campaign.meta_ad_account_id,
            proposed_daily_budget_cents=campaign.daily_budget_cents or 0,
            meta_campaign_id=campaign.id,
        )

    client = _get_client_for_campaign(db, campaign)
    if campaign.external_campaign_id:
        client.update_campaign(campaign.external_campaign_id, status=new_status)
    campaign.status = MetaCampaignStatus(new_status)

    approval.status = ApprovalStatus.EXECUTED
    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=executed_by_user_id,
        action="meta_ads.campaign_status_changed",
        resource_type="MetaCampaign",
        resource_id=str(campaign.id),
        metadata={"new_status": new_status},
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def execute_budget_change(
    db: Session,
    *,
    organization_id: uuid.UUID,
    executed_by_user_id: Optional[uuid.UUID],
    approval_request_id: uuid.UUID,
) -> MetaCampaign:
    approval = db.get(ApprovalRequest, approval_request_id)
    if not approval or approval.organization_id != organization_id:
        raise ExecutionServiceError("Approval request not found")
    if approval.status != ApprovalStatus.APPROVED:
        raise ExecutionServiceError(
            f"Only an APPROVED request can be executed (current status: {approval.status.value})"
        )

    campaign = db.get(MetaCampaign, uuid.UUID(approval.action_payload["meta_campaign_id"]))
    new_budget = approval.action_payload["new_daily_budget_cents"]

    spend_guard.assert_within_limits(
        db,
        meta_ad_account_id=campaign.meta_ad_account_id,
        proposed_daily_budget_cents=new_budget,
        meta_campaign_id=campaign.id,
    )

    client = _get_client_for_campaign(db, campaign)
    if campaign.external_campaign_id:
        client.update_campaign(campaign.external_campaign_id, daily_budget=new_budget)
    campaign.daily_budget_cents = new_budget

    approval.status = ApprovalStatus.EXECUTED
    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=executed_by_user_id,
        action="meta_ads.budget_changed",
        resource_type="MetaCampaign",
        resource_id=str(campaign.id),
        metadata={"new_daily_budget_cents": new_budget},
    )
    db.commit()
    db.refresh(campaign)
    return campaign
