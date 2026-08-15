"""
Campaign CRUD service.

Handles the campaign draft lifecycle that isn't AI generation itself (see
app/campaigns/generation_service.py for that) — creating a draft from
wizard input, listing/fetching drafts (organization-scoped, same tenant
isolation discipline as everywhere else), editing generated content
before approval, and the approve action.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.audit.service import write_audit_log
from app.models.ad_copy_variant import AdCopyVariant
from app.models.campaign import Campaign, CampaignStatus


class CampaignError(Exception):
    """Raised for campaign failures the API layer should turn into 4xx responses."""


def _campaign_query(db: Session):
    return db.query(Campaign).options(
        selectinload(Campaign.strategy),
        selectinload(Campaign.ad_copy_variants),
        selectinload(Campaign.creative_concepts),
        selectinload(Campaign.experiments),
    )


def list_campaigns(db: Session, organization_id: uuid.UUID) -> list[Campaign]:
    return (
        _campaign_query(db)
        .filter(Campaign.organization_id == organization_id)
        .order_by(Campaign.created_at.desc())
        .all()
    )


def get_campaign(db: Session, *, organization_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign:
    campaign = (
        _campaign_query(db)
        .filter(Campaign.id == campaign_id, Campaign.organization_id == organization_id)
        .first()
    )
    if not campaign:
        raise CampaignError("Campaign not found")
    return campaign


def create_campaign_draft(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    data: dict,
) -> Campaign:
    """
    data is expected to already be validated by the caller's Pydantic
    schema (see app/schemas/campaign.py::CampaignCreate) — this function
    just maps validated fields onto the model, it doesn't re-validate.
    """
    campaign = Campaign(organization_id=organization_id, created_by_user_id=actor_user_id, **data)
    db.add(campaign)
    db.flush()

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="campaign.draft_created",
        resource_type="Campaign",
        resource_id=str(campaign.id),
    )

    db.commit()
    db.refresh(campaign)
    return campaign


def update_campaign_draft(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    campaign_id: uuid.UUID,
    updates: dict,
) -> Campaign:
    """
    General-purpose field update for the campaign's own columns (wizard
    inputs). For editing generated ad copy variants, see
    update_ad_copy_variant() below — those are separate rows, not columns
    on Campaign.
    """
    campaign = get_campaign(db, organization_id=organization_id, campaign_id=campaign_id)
    if campaign.status == CampaignStatus.APPROVED:
        raise CampaignError("This campaign has already been approved and can no longer be edited")

    for field, value in updates.items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return campaign


def update_ad_copy_variant(
    db: Session,
    *,
    organization_id: uuid.UUID,
    campaign_id: uuid.UUID,
    variant_id: uuid.UUID,
    updates: dict,
) -> AdCopyVariant:
    """Lets a human edit one generated ad copy variant before approval —
    see wizard step 7 (Review) in the product spec."""
    campaign = get_campaign(db, organization_id=organization_id, campaign_id=campaign_id)
    if campaign.status == CampaignStatus.APPROVED:
        raise CampaignError("This campaign has already been approved and can no longer be edited")

    variant = next((v for v in campaign.ad_copy_variants if v.id == variant_id), None)
    if not variant:
        raise CampaignError("Ad copy variant not found on this campaign")

    for field, value in updates.items():
        setattr(variant, field, value)
    variant.is_edited = True

    db.commit()
    db.refresh(variant)
    return variant


def delete_campaign(db: Session, *, organization_id: uuid.UUID, campaign_id: uuid.UUID) -> None:
    campaign = get_campaign(db, organization_id=organization_id, campaign_id=campaign_id)
    db.delete(campaign)
    db.commit()


def approve_campaign(
    db: Session, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID | None, campaign_id: uuid.UUID
) -> Campaign:
    """
    Wizard step 8. A lightweight status change only — see
    app/models/campaign.py's module docstring for why this is NOT routed
    through ApprovalRequest (that model is reserved for actions with real
    external side effects; nothing launches here).
    """
    campaign = get_campaign(db, organization_id=organization_id, campaign_id=campaign_id)
    if campaign.status != CampaignStatus.GENERATED:
        raise CampaignError(
            "Only a fully generated campaign can be approved "
            f"(current status: {campaign.status.value})"
        )

    campaign.status = CampaignStatus.APPROVED
    campaign.approved_at = datetime.now(timezone.utc)
    campaign.approved_by_user_id = actor_user_id

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="campaign.approved",
        resource_type="Campaign",
        resource_id=str(campaign.id),
    )

    db.commit()
    db.refresh(campaign)
    return campaign
