"""
Pydantic schemas for authentication endpoints.

Note: no password field is ever included in a response schema — only in
request (input) schemas. This is a deliberate guard against accidentally
leaking hashed_password through an endpoint response.
"""
import uuid

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=1, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    phone: str | None
    timezone: str | None
    is_active: bool
    is_email_verified: bool

    model_config = {"from_attributes": True}


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    """Generic ack response for endpoints that don't return a resource —
    e.g. forgot-password, which must respond identically whether or not the
    email exists, to avoid leaking account existence."""

    message: str
