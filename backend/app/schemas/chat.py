import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ChatMessagePublic(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageResponse(BaseModel):
    conversation_id: uuid.UUID
    message: ChatMessagePublic


class ConversationPublic(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationPublic):
    messages: list[ChatMessagePublic]
