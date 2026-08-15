"""
Business profile settings endpoints — currently just brand voice.

Kept separate from onboarding.py: brand voice isn't onboarding step 11
(see app/models/business_profile.py's own comment on why), it's a
content-generation setting a business is more likely to revisit than the
one-time onboarding answers, so it gets its own settings surface here.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.onboarding.service import get_or_create_business_profile, update_brand_voice
from app.schemas.business_profile import BrandVoiceUpdate, BusinessProfilePublic

router = APIRouter(prefix="/business-profile", tags=["business-profile"])


@router.get("/brand-voice", response_model=BusinessProfilePublic)
def get_brand_voice(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return get_or_create_business_profile(db, member.organization_id)


@router.put("/brand-voice", response_model=BusinessProfilePublic)
def set_brand_voice(
    payload: BrandVoiceUpdate,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    """
    Gated on can_manage_content — the same permission that gates content
    creation/editing (Owner/Admin/Manager/Content Manager have it), since
    brand voice exists specifically to shape content generation and a
    role that can't manage content has no reason to change the voice
    every future generation call will use.
    """
    return update_brand_voice(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        brand_voice=payload.brand_voice,
        brand_voice_custom=payload.brand_voice_custom,
    )
