import uuid

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_agency: bool = False


class OrganizationPublic(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan_type: str
    is_agency: bool

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    """Partial update — currently just the business name (onboarding step 1)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
