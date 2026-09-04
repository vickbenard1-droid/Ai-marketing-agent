import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.campaign_autonomy_settings import AutonomyLevel
from app.models.optimization_decision import DecisionRisk, DecisionStatus, OptimizationActionType


class AutonomySettingsPublic(BaseModel):
    meta_campaign_id: uuid.UUID
    autonomy_level: AutonomyLevel
    max_daily_spend_cents: Optional[int]
    max_budget_increase_percent: Optional[int]
    max_automated_actions_per_day: Optional[int]
    auto_executable_action_types: list
    is_emergency_stopped: bool
    emergency_stop_reason: Optional[str]

    model_config = {"from_attributes": True}


class SetAutonomySettingsRequest(BaseModel):
    autonomy_level: AutonomyLevel
    max_daily_spend_cents: Optional[int] = Field(default=None, ge=0)
    max_budget_increase_percent: Optional[int] = Field(default=None, ge=0, le=1000)
    max_automated_actions_per_day: Optional[int] = Field(default=None, ge=0)
    auto_executable_action_types: list = Field(default_factory=list)


class SetEmergencyStopRequest(BaseModel):
    stopped: bool
    reason: Optional[str] = Field(default=None, max_length=500)


class WhitelistEntryPublic(BaseModel):
    id: uuid.UUID
    meta_campaign_id: uuid.UUID
    added_by_user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class OptimizationDecisionPublic(BaseModel):
    id: uuid.UUID
    meta_campaign_id: uuid.UUID
    observation: str
    evidence_json: dict
    action_type: OptimizationActionType
    proposed_action: str
    action_payload: dict
    expected_outcome: str
    confidence: float
    risk: DecisionRisk
    required_permission: str
    status: DecisionStatus
    resulting_approval_request_id: Optional[uuid.UUID]
    outcome_json: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewDecisionRequest(BaseModel):
    approve: bool
    new_daily_budget_cents: Optional[int] = Field(default=None, ge=0)


class ScanCampaignResponse(BaseModel):
    meta_campaign_id: uuid.UUID
    decisions_created: list
    errors: list
