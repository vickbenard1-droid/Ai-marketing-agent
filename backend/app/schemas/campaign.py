"""
Schemas for the campaign builder (Week 4).

CampaignCreate collects wizard steps 1-6 in one request rather than one
schema per step (unlike onboarding's OnboardingStepX pattern) — the
campaign wizard's steps are all optional/independent fields on the same
draft, saved together when the user reaches Review, rather than each
being its own persisted resource the way onboarding steps are. Business
(step 1) isn't its own field here since it's implicit in the
organization context (X-Organization-Id), matching how business name
already works for onboarding.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.campaign import CampaignStatus, MarketingObjective
from app.models.creative_concept import CreativeConceptType
from app.models.experiment import ExperimentDimension


class CampaignCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    product_price: int | None = Field(default=None, ge=0)
    product_description: str | None = Field(default=None, max_length=4000)

    objective: MarketingObjective
    desired_outcome_count: int | None = Field(default=None, ge=0)

    target_location: str | None = Field(default=None, max_length=255)
    target_audience: str | None = Field(default=None, max_length=4000)
    existing_customer_info: str | None = Field(default=None, max_length=4000)

    budget_amount: int | None = Field(default=None, ge=0)
    budget_currency: str = Field(default="USD", min_length=3, max_length=3)
    duration_days: int | None = Field(default=None, ge=1, le=365)

    landing_page_url: str | None = Field(default=None, max_length=500)


class CampaignUpdate(BaseModel):
    """All optional — partial update (PATCH semantics), same pattern as
    UserProfileUpdate. Blocked server-side once the campaign is approved
    (see app/campaigns/service.py::update_campaign_draft)."""

    product_name: str | None = Field(default=None, min_length=1, max_length=255)
    product_price: int | None = Field(default=None, ge=0)
    product_description: str | None = Field(default=None, max_length=4000)
    objective: MarketingObjective | None = None
    desired_outcome_count: int | None = Field(default=None, ge=0)
    target_location: str | None = Field(default=None, max_length=255)
    target_audience: str | None = Field(default=None, max_length=4000)
    existing_customer_info: str | None = Field(default=None, max_length=4000)
    budget_amount: int | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, min_length=3, max_length=3)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    landing_page_url: str | None = Field(default=None, max_length=500)


class AdCopyVariantPublic(BaseModel):
    id: uuid.UUID
    variant_number: int
    headline: str
    primary_text: str
    description: str | None
    call_to_action: str
    is_edited: bool

    model_config = {"from_attributes": True}


class AdCopyVariantUpdate(BaseModel):
    headline: str | None = Field(default=None, min_length=1, max_length=255)
    primary_text: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, max_length=500)
    call_to_action: str | None = Field(default=None, min_length=1, max_length=100)


class CreativeConceptPublic(BaseModel):
    id: uuid.UUID
    concept_type: CreativeConceptType
    title: str
    description: str

    model_config = {"from_attributes": True}


class CampaignStrategyPublic(BaseModel):
    strategy: dict
    audience: dict
    budget_strategy: dict

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, model) -> "CampaignStrategyPublic":
        """CampaignStrategy's columns are strategy_json/audience_json/
        budget_strategy_json — this adapts the ORM's column names to the
        API's shorter, response-facing key names without needing a
        Pydantic alias configuration for three fields used nowhere else."""
        return cls(
            strategy=model.strategy_json,
            audience=model.audience_json,
            budget_strategy=model.budget_strategy_json,
        )


class CampaignPublic(BaseModel):
    id: uuid.UUID
    status: CampaignStatus
    product_name: str
    product_price: int | None
    product_description: str | None
    objective: MarketingObjective
    desired_outcome_count: int | None
    target_location: str | None
    target_audience: str | None
    existing_customer_info: str | None
    budget_amount: int | None
    budget_currency: str
    duration_days: int | None
    landing_page_url: str | None
    generated_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignDetail(CampaignPublic):
    strategy: CampaignStrategyPublic | None
    ad_copy_variants: list[AdCopyVariantPublic]
    creative_concepts: list[CreativeConceptPublic]

    @classmethod
    def from_model(cls, campaign) -> "CampaignDetail":
        return cls(
            **CampaignPublic.model_validate(campaign).model_dump(),
            strategy=CampaignStrategyPublic.from_model(campaign.strategy) if campaign.strategy else None,
            ad_copy_variants=[AdCopyVariantPublic.model_validate(v) for v in campaign.ad_copy_variants],
            creative_concepts=[CreativeConceptPublic.model_validate(c) for c in campaign.creative_concepts],
        )


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dimension: ExperimentDimension
    description: str | None = Field(default=None, max_length=2000)
    # For dimension=headline/hook/creative: UUIDs of AdCopyVariant or
    # CreativeConcept rows on this campaign. For dimension=audience:
    # freeform strings describing each audience variant being tested (no
    # "Audience" row/table exists — see app/models/experiment.py).
    variant_ids: list[str] = Field(min_length=2, max_length=10)

    @field_validator("variant_ids")
    @classmethod
    def _no_blank_entries(cls, value: list[str]) -> list[str]:
        if any(not v.strip() for v in value):
            raise ValueError("variant_ids entries cannot be blank")
        return value


class ExperimentPublic(BaseModel):
    id: uuid.UUID
    name: str
    dimension: ExperimentDimension
    description: str | None
    variant_ids: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}
