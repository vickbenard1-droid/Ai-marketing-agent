import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.campaigns.experiment_service import ExperimentError, create_experiment, list_experiments
from app.campaigns.service import CampaignError
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.campaign import ExperimentCreate, ExperimentPublic

router = APIRouter(prefix="/campaigns/{campaign_id}/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentPublic])
def list_campaign_experiments(
    campaign_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        return list_experiments(db, organization_id=member.organization_id, campaign_id=campaign_id)
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=ExperimentPublic, status_code=status.HTTP_201_CREATED)
def create_campaign_experiment(
    campaign_id: uuid.UUID,
    payload: ExperimentCreate,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return create_experiment(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            campaign_id=campaign_id,
            name=payload.name,
            dimension=payload.dimension,
            description=payload.description,
            variant_ids=payload.variant_ids,
        )
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ExperimentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
