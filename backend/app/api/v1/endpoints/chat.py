"""
Chat endpoints.

Sending a message is gated on can_execute_ai_actions (same reasoning as
agents.py — every message incurs real AI cost). Listing/reading past
conversations only requires org membership, matching the read-vs-mutate
split used elsewhere (e.g. members.py: anyone can list, only
can_manage_members can invite).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import uuid

from app.ai_chat.service import ChatError, get_conversation, list_conversations, send_message
from app.ai_providers.base import AIProviderError
from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.chat import (
    ConversationDetail,
    ConversationPublic,
    SendMessageRequest,
    SendMessageResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationPublic])
def list_my_conversations(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return list_conversations(db, organization_id=member.organization_id, user_id=member.user_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_my_conversation(
    conversation_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        return get_conversation(
            db,
            organization_id=member.organization_id,
            user_id=member.user_id,
            conversation_id=conversation_id,
        )
    except ChatError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/messages", response_model=SendMessageResponse)
def send_chat_message(
    payload: SendMessageRequest,
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
    db: Session = Depends(get_db),
):
    try:
        assistant_message = send_message(
            db,
            organization_id=member.organization_id,
            user_id=member.user_id,
            message=payload.message,
            conversation_id=payload.conversation_id,
        )
    except ChatError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AIProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return SendMessageResponse(
        conversation_id=assistant_message.conversation_id, message=assistant_message
    )
