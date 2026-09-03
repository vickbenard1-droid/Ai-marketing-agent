import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.approval_request import ApprovalActionType, ApprovalStatus
from app.models.meta_campaign import MetaCampaignObjective, MetaCampaignStatus


class MetaAdAccountPublic(BaseModel):
    id: uuid.UUID
    external_ad_account_id: str
    name: str
    currency: str
    timezone_name: str

    model_config = {"from_attributes": True}


class ConnectMetaAdAccountRequest(BaseModel):
    connected_account_id: uuid.UUID
    external_ad_account_id: str
    name: str
    currency: str
    timezone_name: str


class AdAccountSpendLimitPublic(BaseModel):
    meta_ad_account_id: uuid.UUID
    daily_spend_limit_cents: int
    is_emergency_stopped: bool
    emergency_stop_reason: Optional[str]

    model_config = {"from_attributes": True}


class SetSpendLimitRequest(BaseModel):
    daily_spend_limit_cents: int = Field(ge=0)


class SetEmergencyStopRequest(BaseModel):
    stopped: bool
    reason: Optional[str] = Field(default=None, max_length=500)


class MetaCampaignPublic(BaseModel):
    id: uuid.UUID
    name: str
    objective: MetaCampaignObjective
    status: MetaCampaignStatus
    daily_budget_cents: Optional[int]
    lifetime_budget_cents: Optional[int]
    external_campaign_id: Optional[str]

    model_config = {"from_attributes": True}


class RequestStatusChangeRequest(BaseModel):
    new_status: str = Field(pattern="^(ACTIVE|PAUSED)$")


class RequestBudgetChangeRequest(BaseModel):
    new_daily_budget_cents: int = Field(ge=0)


class ApprovalRequestPublic(BaseModel):
    id: uuid.UUID
    action_type: ApprovalActionType
    action_payload: dict
    status: ApprovalStatus
    requested_by_user_id: Optional[uuid.UUID]
    reviewed_by_user_id: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewApprovalRequest(BaseModel):
    approve: bool
    review_notes: Optional[str] = Field(default=None, max_length=2000)


class MetaInsightSnapshotPublic(BaseModel):
    date: date_type
    impressions: int
    clicks: int
    spend_cents: int
    reach: Optional[int]
    leads_count: Optional[int]
    purchases_count: Optional[int]
    revenue_cents: Optional[int]
    currency: str

    model_config = {"from_attributes": True}


class MetaCampaignProposalPublic(BaseModel):
    name: str
    objective: MetaCampaignObjective
    daily_budget_cents: Optional[int]
    targeting_spec: Optional[dict]
    unresolved_fields: list
