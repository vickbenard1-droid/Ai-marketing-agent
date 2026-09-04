import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.lead import LeadSource, LeadStage
from app.models.lead_follow_up import FollowUpChannel, FollowUpStatus


class LeadPublic(BaseModel):
    id: uuid.UUID
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    source: LeadSource
    source_external_id: Optional[str]
    attributed_meta_campaign_id: Optional[uuid.UUID]
    stage: LeadStage
    product_interest: Optional[str]
    disclosed_budget_cents: Optional[int]
    score: Optional[int]
    score_factors_json: Optional[dict]
    assigned_to_user_id: Optional[uuid.UUID]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateManualLeadRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    product_interest: Optional[str] = Field(default=None, max_length=500)
    disclosed_budget_cents: Optional[int] = Field(default=None, ge=0)
    attributed_meta_campaign_id: Optional[uuid.UUID] = None


class TransitionStageRequest(BaseModel):
    to_stage: LeadStage
    note: Optional[str] = Field(default=None, max_length=2000)


class AssignLeadRequest(BaseModel):
    assigned_to_user_id: Optional[uuid.UUID] = None


class UpdateLeadNotesRequest(BaseModel):
    notes: str = Field(max_length=10000)


class LeadStageTransitionPublic(BaseModel):
    id: uuid.UUID
    from_stage: Optional[LeadStage]
    to_stage: LeadStage
    changed_by_user_id: Optional[uuid.UUID]
    changed_at: datetime
    note: Optional[str]

    model_config = {"from_attributes": True}


class QualificationCriteriaPublic(BaseModel):
    minimum_score: int
    minimum_disclosed_budget_cents: Optional[int]
    require_product_interest: bool


class SetQualificationCriteriaRequest(BaseModel):
    minimum_score: int = Field(ge=0, le=100)
    minimum_disclosed_budget_cents: Optional[int] = Field(default=None, ge=0)
    require_product_interest: bool = False


class QualificationResultPublic(BaseModel):
    qualifies: bool
    reasons: list


class LeadFollowUpPublic(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    channel: FollowUpChannel
    subject: Optional[str]
    body: str
    status: FollowUpStatus
    send_error: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateFollowUpRequest(BaseModel):
    channel: FollowUpChannel
    tone: Optional[str] = Field(default=None, max_length=200)


class SalesAnalyticsPublic(BaseModel):
    date_range: dict
    leads: int
    qualified_leads: int
    sales: int
    conversion_rate: Optional[float]
    revenue_cents: Optional[int]
    spend_cents: int
    cost_per_sale_cents: Optional[float]
    roas: Optional[float]
    customer_acquisition_cost_cents: Optional[float]
    note: str


class AskSalesQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    date_start: str
    date_stop: str


class SalesAgentAnswerPublic(BaseModel):
    answer_text: str
    data_used: dict
