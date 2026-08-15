"""
Campaign generation endpoint, kept separate from campaigns.py (basic CRUD)
because it's gated on a different permission — can_execute_ai_actions,
not can_manage_campaigns — since this is the action that actually spends
AI provider budget. A Manager can create/edit a campaign draft without
that permission; generating (or regenerating) its content requires it.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.campaigns.generation_service import CampaignGenerationError, generate_campaign
from app.campaigns.service import CampaignError
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.campaign import CampaignDetail

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("/{campaign_id}/generate", response_model=CampaignDetail)
def generate(
    campaign_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
    db: Session = Depends(get_db),
):
    """
    Generates (or regenerates) a campaign's strategy, audience plan, ad
    copy variants, creative concepts, and budget plan. Safe to call again
    on an already-generated (but not yet approved) campaign — regeneration
    replaces the prior content wholesale (see
    generation_service.py::_persist_generated_campaign).
    """
    try:
        campaign = generate_campaign(
            db, organization_id=member.organization_id, actor_user_id=member.user_id, campaign_id=campaign_id
        )
    except CampaignError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CampaignGenerationError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return CampaignDetail.from_model(campaign)
