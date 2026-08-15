"""
Schemas for the business onboarding flow (Week 2).

One schema per onboarding step (StepNWebsite, StepNIndustry, ...) rather
than a single giant "update everything" schema — the frontend saves one
step at a time as the user progresses, and per-step schemas let each save
validate only what that step actually collects. BusinessProfilePublic is
the read-side view returned after any step, and by the profile/dashboard
endpoints.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.business_profile import BrandVoice, MarketingGoal


class OnboardingStepWebsite(BaseModel):
    website_url: str | None = Field(default=None, max_length=500)


class OnboardingStepIndustry(BaseModel):
    industry: str = Field(min_length=1, max_length=150)


class OnboardingStepCountry(BaseModel):
    country: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2, e.g. 'US'")


class OnboardingStepProductsServices(BaseModel):
    products_services: str = Field(min_length=1, max_length=4000)


class OnboardingStepTargetCustomers(BaseModel):
    target_customers: str = Field(min_length=1, max_length=4000)


class OnboardingStepMarketingGoal(BaseModel):
    marketing_goal: MarketingGoal


class OnboardingStepBudget(BaseModel):
    monthly_ad_budget: int = Field(ge=0, le=100_000_000)
    budget_currency: str = Field(default="USD", min_length=3, max_length=3)


class OnboardingStepSocialPlatforms(BaseModel):
    social_platforms: list[str] = Field(default_factory=list, max_length=20)


class OnboardingStepAdvertisingPlatforms(BaseModel):
    advertising_platforms: list[str] = Field(default_factory=list, max_length=20)


class BusinessProfilePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    website_url: str | None
    industry: str | None
    country: str | None
    products_services: str | None
    target_customers: str | None
    marketing_goal: MarketingGoal | None
    monthly_ad_budget: int | None
    budget_currency: str
    social_platforms: list[str] | None
    advertising_platforms: list[str] | None
    onboarding_completed_at: datetime | None
    onboarding_current_step: int
    brand_voice: BrandVoice | None
    brand_voice_custom: str | None

    model_config = {"from_attributes": True}


class BrandVoiceUpdate(BaseModel):
    """
    Week 5: lets a business configure its brand voice independent of the
    onboarding wizard (see app/models/business_profile.py's own comment
    on why this isn't onboarding step 11). brand_voice_custom is only
    meaningful when brand_voice=CUSTOM but isn't validated as
    required-together here — the service layer stores whatever's given
    and app.knowledge.service._resolve_brand_voice() already handles a
    CUSTOM value with no custom text (falls back to None) gracefully.
    """

    brand_voice: BrandVoice
    brand_voice_custom: str | None = Field(default=None, max_length=1000)
