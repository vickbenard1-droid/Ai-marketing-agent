from pydantic import BaseModel, Field


class UserProfileUpdate(BaseModel):
    """
    All fields optional — this is a partial update (PATCH semantics).
    Email is deliberately excluded: changing it would need its own
    re-verification flow, out of scope for Week 2 (see docs/ARCHITECTURE.md
    "not built yet").
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    timezone: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=1000)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
