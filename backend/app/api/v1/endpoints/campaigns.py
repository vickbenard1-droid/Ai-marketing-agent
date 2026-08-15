"""
Campaign endpoints.

Reading (list/get) requires only org membership, matching the read-vs-
mutate split used everywhere else in this app (e.g. members.py). Creating
and editing a draft's own fields is gated on can_manage_campaigns — the
permission flag seeded back in Week 2 specifically anticipating this
feature (Owner/Admin/Manager have it, Content Manager/Analyst/Viewer
don't). Generation and regeneration are handled in
app/api/v1/endpoints/campaign_generation.py, gated on
can_execute_ai_actions instead, since that's the action that actually
costs money.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.campaigns.service import (
    CampaignError,
    approve_campaign,
    create_campaign_draft,
    delete_campaign,
    get_campaign,
    list_campaigns,
    update_ad_copy_variant,
    update_campaign_draft,
)
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.auth import MessageResponse
from app.schemas.campaign import (
    AdCopyVariantPublic,
    AdCopyVariantUpdate,
    CampaignCreate,
    CampaignDetail,
    CampaignPublic,
    CampaignUpdate,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignPublic])
def list_my_campaigns(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return list_campaigns(db, member.organization_id)


@router.post("", response_model=CampaignPublic, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignCreate,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    return create_campaign_draft(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        data=payload.model_dump(),
    )


@router.get("/{campaign_id}", response_model=CampaignDetail)
def get_campaign_detail(
    campaign_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        campaign = get_campaign(db, organization_id=member.organization_id, campaign_id=campaign_id)
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return CampaignDetail.from_model(campaign)


@router.patch("/{campaign_id}", response_model=CampaignPublic)
def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return update_campaign_draft(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            campaign_id=campaign_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{campaign_id}", response_model=MessageResponse)
def delete_campaign_draft(
    campaign_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        delete_campaign(db, organization_id=member.organization_id, campaign_id=campaign_id)
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return MessageResponse(message="Campaign deleted")


@router.patch("/{campaign_id}/ad-copy-variants/{variant_id}", response_model=AdCopyVariantPublic)
def update_variant(
    campaign_id: uuid.UUID,
    variant_id: uuid.UUID,
    payload: AdCopyVariantUpdate,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return update_ad_copy_variant(
            db,
            organization_id=member.organization_id,
            campaign_id=campaign_id,
            variant_id=variant_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{campaign_id}/approve", response_model=CampaignPublic)
def approve(
    campaign_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return approve_campaign(
            db, organization_id=member.organization_id, actor_user_id=member.user_id, campaign_id=campaign_id
        )
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
