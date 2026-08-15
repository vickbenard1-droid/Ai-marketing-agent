"""
Schemas for connected social accounts (Week 6).

ConnectedAccountPublic deliberately has NO field for
encrypted_credentials, access_token, or refresh_token - this is the
schema-level half of "never expose access tokens to the frontend" (the
other half is app/oauth/service.py never returning a decrypted token to
begin with). Anyone extending this schema should treat adding a token
field here as a security bug, not a feature.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.connected_account import ConnectionStatus, PlatformType


class ConnectedAccountPublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    platform: PlatformType
    status: ConnectionStatus
    external_account_id: str | None
    external_account_name: str | None
    granted_scopes: str | None
    token_expires_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StartConnectRequest(BaseModel):
    project_id: uuid.UUID


class StartConnectResponse(BaseModel):
    authorize_url: str


class SupportedPlatform(BaseModel):
    platform: PlatformType
    display_name: str
    configured: bool  # whether this deployment has client credentials set for it
