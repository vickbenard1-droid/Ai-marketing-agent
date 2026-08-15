import uuid

from pydantic import BaseModel, EmailStr, Field


class RolePublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class OrganizationMemberPublic(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role: RolePublic

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    """
    Week 2 scope: invites an *existing* user by email directly into the
    organization (no invite-token/email-accept flow yet — see
    docs/ARCHITECTURE.md "not built yet"). If no account exists for the
    email, the request fails with a clear message rather than silently
    creating one, since a real invite-and-signup flow deserves its own
    design pass rather than being improvised here.
    """

    email: EmailStr
    role_name: str = Field(description="One of: owner, admin, manager, analyst, content_manager, viewer")


class UpdateMemberRoleRequest(BaseModel):
    role_name: str = Field(description="One of: owner, admin, manager, analyst, content_manager, viewer")
