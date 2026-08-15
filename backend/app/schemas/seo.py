import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GenerateSEORequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    content_id: uuid.UUID | None = None


class SEOContentPublic(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID | None
    topic: str
    primary_keyword: str | None
    secondary_keywords: list[str] | None
    search_intent: str | None
    seo_title: str | None
    meta_description: str | None
    url_slug: str | None
    h1: str | None
    h2_structure: list[str] | None
    internal_linking_suggestions: list[str] | None
    image_alt_text: str | None
    hashtags: list[str] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
