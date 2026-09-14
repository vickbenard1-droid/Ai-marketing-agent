import uuid
from typing import Optional

from pydantic import BaseModel


class SubscriptionPlanPublic(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    monthly_price_cents: int
    max_ai_tokens_per_month: Optional[int]
    max_campaigns: Optional[int]
    max_connected_accounts: Optional[int]
    max_content_generations_per_month: Optional[int]
    max_automated_actions_per_month: Optional[int]

    model_config = {"from_attributes": True}


class UsageCategoryPublic(BaseModel):
    category: str
    current: int
    limit: Optional[int]  # None means unlimited


class CurrentPlanAndUsagePublic(BaseModel):
    plan: SubscriptionPlanPublic
    usage: list[UsageCategoryPublic]


class ChangePlanRequest(BaseModel):
    plan_name: str
