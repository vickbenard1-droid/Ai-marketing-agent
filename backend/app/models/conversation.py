"""
Conversation and ChatMessage models.

One Conversation per chat thread, organization-scoped (never user-scoped
alone — see app/ai_chat/service.py for why the org boundary matters here
just as much as it does everywhere else in this app). ChatMessage rows are
the turn-by-turn history; role mirrors the AIMessage.role values used by
the provider layer (app/ai_providers/base.py) so a conversation's history
can be replayed directly into AIProvider.generate() without translation.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Auto-generated from the first message (see app/ai_chat/service.py) so
    # the conversation list has something readable without an extra
    # summarization call. Nullable while a conversation has no messages yet.
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} org={self.organization_id}>"


class ChatMessage(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole, name="chat_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.role} conversation={self.conversation_id}>"
