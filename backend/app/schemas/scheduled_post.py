import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.scheduled_post import ScheduledPostStatus


class CreateDraftPostRequest(BaseModel):
    content_id: uuid.UUID
    connected_account_id: uuid.UUID


class SchedulePostRequest(BaseModel):
    scheduled_for: datetime


class ScheduledPostPublic(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID
    connected_account_id: uuid.UUID
    status: ScheduledPostStatus
    scheduled_for: datetime | None
    published_at: datetime | None
    external_post_id: str | None
    external_post_url: str | None
    retry_count: int
    ai_recommended_post_time: datetime | None
    ai_recommended_platform: str | None
    ai_recommended_format: str | None
    ai_recommended_hashtags: list[str] | None
    ai_recommendation_rationale: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublishingLogPublic(BaseModel):
    id: uuid.UUID
    outcome: str
    request_summary: str
    error_message: str | None
    attempt_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduledPostDetail(ScheduledPostPublic):
    publishing_logs: list[PublishingLogPublic]
