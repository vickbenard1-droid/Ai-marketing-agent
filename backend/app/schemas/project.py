import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    industry: str | None = Field(default=None, max_length=100)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    industry: str | None = Field(default=None, max_length=100)


class ProjectPublic(BaseModel):
    id: uuid.UUID
    name: str
    website_url: str | None
    description: str | None
    industry: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
