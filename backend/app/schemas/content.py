import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.business_profile import BrandVoice
from app.models.content import ContentStatus, ContentType


class GenerateContentRequest(BaseModel):
    content_type: ContentType
    source_text: str | None = Field(default=None, max_length=8000)
    source_url: str | None = Field(default=None, max_length=500)
    source_asset_id: uuid.UUID | None = None

    @field_validator("source_url")
    @classmethod
    def _validate_has_scheme(cls, value: str | None) -> str | None:
        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("source_url must start with http:// or https://")
        return value


class ContentUpdate(BaseModel):
    """Partial update for a draft's own fields - editing the generated
    body/title before approval. Blocked server-side once approved, same
    pattern as CampaignUpdate."""

    title: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, min_length=1)


class ContentPublic(BaseModel):
    id: uuid.UUID
    content_type: ContentType
    status: ContentStatus
    title: str | None
    body: str
    source_text: str | None
    source_url: str | None
    source_asset_id: uuid.UUID | None
    brand_voice_used: BrandVoice | None
    repurpose_batch_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepurposeRequest(BaseModel):
    source_text: str | None = Field(default=None, max_length=8000)
    source_url: str | None = Field(default=None, max_length=500)
    source_asset_id: uuid.UUID | None = None

    @field_validator("source_url")
    @classmethod
    def _validate_has_scheme(cls, value: str | None) -> str | None:
        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("source_url must start with http:// or https://")
        return value


class RepurposeBatchPublic(BaseModel):
    id: uuid.UUID
    source_text: str | None
    source_url: str | None
    source_asset_id: uuid.UUID | None
    created_at: datetime
    items: list[ContentPublic]

    model_config = {"from_attributes": True}
