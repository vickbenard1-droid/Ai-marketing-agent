import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.agent_activity_log import ActivityStatus
from app.models.agent_decision import DecisionOutcome
from app.models.orchestration_run import OrchestrationRunStatus


class CreateRunRequest(BaseModel):
    goal_text: str = Field(min_length=1, max_length=2000)


class OrchestrationRunPublic(BaseModel):
    id: uuid.UUID
    goal_text: str
    plan_json: list
    current_step: int
    status: OrchestrationRunStatus
    final_summary: Optional[str]
    requested_by_user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApproveStepRequest(BaseModel):
    approve: bool
    agent_kwargs: dict = Field(default_factory=dict)


class AgentActivityLogPublic(BaseModel):
    id: uuid.UUID
    orchestration_run_id: Optional[uuid.UUID]
    agent_name: str
    step_number: Optional[int]
    action_description: str
    reasoning: Optional[str]
    data_used_json: dict
    recommendation: Optional[str]
    execution_result_json: Optional[dict]
    status: ActivityStatus
    requires_approval: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentDecisionPublic(BaseModel):
    id: uuid.UUID
    agent_name: str
    goal_description: Optional[str]
    decision_summary: str
    outcome: DecisionOutcome
    outcome_notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentSummaryPublic(BaseModel):
    name: str
    description: str


class RelevantMemoryPublic(BaseModel):
    business_knowledge: str
    recent_performance: dict
    successful_strategies: list
    failed_strategies: list
    recent_customer_summary: dict
