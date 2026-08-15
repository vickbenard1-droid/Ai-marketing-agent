"""
Onboarding business logic: get-or-create the org's BusinessProfile, save
one step at a time, mark onboarding complete.

TOTAL_STEPS = 10 matches the product spec exactly (business name is step 1
but lives on Organization.name, not here — see BusinessProfile's module
docstring). Steps 2-10 below map 1:1 onto BusinessProfile columns.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.models.business_profile import BusinessProfile

TOTAL_STEPS = 10


def get_or_create_business_profile(db: Session, organization_id) -> BusinessProfile:
    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.organization_id == organization_id)
        .first()
    )
    if profile:
        return profile

    profile = BusinessProfile(organization_id=organization_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def save_step(
    db: Session,
    *,
    organization_id,
    actor_user_id,
    step_number: int,
    fields: dict,
) -> BusinessProfile:
    """
    Applies `fields` to the org's BusinessProfile and advances
    onboarding_current_step if this step is further than what's recorded —
    never regresses the step counter if the user revisits an earlier step
    (e.g. via browser back button) after having already gone further.
    """
    profile = get_or_create_business_profile(db, organization_id)

    for key, value in fields.items():
        setattr(profile, key, value)

    if step_number > profile.onboarding_current_step:
        profile.onboarding_current_step = step_number

    db.commit()
    db.refresh(profile)
    return profile


def complete_onboarding(db: Session, *, organization_id, actor_user_id) -> BusinessProfile:
    profile = get_or_create_business_profile(db, organization_id)
    profile.onboarding_completed_at = datetime.now(timezone.utc)
    profile.onboarding_current_step = TOTAL_STEPS

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="onboarding.completed",
        resource_type="BusinessProfile",
        resource_id=str(profile.id),
    )

    db.commit()
    db.refresh(profile)
    return profile


def update_brand_voice(
    db: Session, *, organization_id, actor_user_id, brand_voice, brand_voice_custom: str | None
) -> BusinessProfile:
    """
    Week 5. Not part of the 10-step onboarding flow (no step_number, no
    onboarding_current_step advancement) — brand voice is an
    always-editable content-generation setting, not a one-time wizard
    answer. See BrandVoiceUpdate's docstring for why brand_voice_custom
    isn't validated as required when brand_voice=CUSTOM.
    """
    profile = get_or_create_business_profile(db, organization_id)
    profile.brand_voice = brand_voice
    profile.brand_voice_custom = brand_voice_custom

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="business_profile.brand_voice_updated",
        resource_type="BusinessProfile",
        resource_id=str(profile.id),
        metadata={"brand_voice": brand_voice.value},
    )

    db.commit()
    db.refresh(profile)
    return profile
