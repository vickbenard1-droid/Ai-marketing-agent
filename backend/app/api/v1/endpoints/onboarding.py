"""
Onboarding endpoints.

Step 1 (business name) is Organization.name itself — see PATCH
/organizations/{id} in organizations.py, not duplicated here. Steps 2-10
below each save one field group of BusinessProfile and are idempotent
(calling the same step twice just overwrites it, which is what "the user
went back and changed their answer" needs).

All routes require org membership (get_current_org_member) — any member can
progress onboarding, not just the owner, since typically the person who
registered is filling this out themselves. Completing onboarding doesn't
require a special permission for the same reason.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.onboarding.service import complete_onboarding, get_or_create_business_profile, save_step
from app.schemas.business_profile import (
    BusinessProfilePublic,
    OnboardingStepAdvertisingPlatforms,
    OnboardingStepBudget,
    OnboardingStepCountry,
    OnboardingStepIndustry,
    OnboardingStepMarketingGoal,
    OnboardingStepProductsServices,
    OnboardingStepSocialPlatforms,
    OnboardingStepTargetCustomers,
    OnboardingStepWebsite,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("", response_model=BusinessProfilePublic)
def get_onboarding_state(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return get_or_create_business_profile(db, member.organization_id)


@router.put("/step-2-website", response_model=BusinessProfilePublic)
def step_2_website(
    payload: OnboardingStepWebsite,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=2,
        fields=payload.model_dump(),
    )


@router.put("/step-3-industry", response_model=BusinessProfilePublic)
def step_3_industry(
    payload: OnboardingStepIndustry,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=3,
        fields=payload.model_dump(),
    )


@router.put("/step-4-country", response_model=BusinessProfilePublic)
def step_4_country(
    payload: OnboardingStepCountry,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=4,
        fields=payload.model_dump(),
    )


@router.put("/step-5-products-services", response_model=BusinessProfilePublic)
def step_5_products_services(
    payload: OnboardingStepProductsServices,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=5,
        fields=payload.model_dump(),
    )


@router.put("/step-6-target-customers", response_model=BusinessProfilePublic)
def step_6_target_customers(
    payload: OnboardingStepTargetCustomers,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=6,
        fields=payload.model_dump(),
    )


@router.put("/step-7-marketing-goal", response_model=BusinessProfilePublic)
def step_7_marketing_goal(
    payload: OnboardingStepMarketingGoal,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=7,
        fields=payload.model_dump(),
    )


@router.put("/step-8-budget", response_model=BusinessProfilePublic)
def step_8_budget(
    payload: OnboardingStepBudget,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=8,
        fields=payload.model_dump(),
    )


@router.put("/step-9-social-platforms", response_model=BusinessProfilePublic)
def step_9_social_platforms(
    payload: OnboardingStepSocialPlatforms,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=9,
        fields=payload.model_dump(),
    )


@router.put("/step-10-advertising-platforms", response_model=BusinessProfilePublic)
def step_10_advertising_platforms(
    payload: OnboardingStepAdvertisingPlatforms,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return save_step(
        db,
        organization_id=member.organization_id,
        actor_user_id=member.user_id,
        step_number=10,
        fields=payload.model_dump(),
    )


@router.post("/complete", response_model=BusinessProfilePublic)
def complete(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return complete_onboarding(db, organization_id=member.organization_id, actor_user_id=member.user_id)
