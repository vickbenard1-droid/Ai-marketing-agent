"""
AI chat service.

Conversations and their messages are organization-scoped (via
Conversation.organization_id, enforced by every function below taking
organization_id and filtering on it) — the same tenant-isolation
discipline as everything else in this app. A user can only see/continue
conversations that belong to their active organization, never another
org's, even if they're a member of both.

History replay: when continuing a conversation, every prior ChatMessage is
sent back to the provider as context (see send_message()'s message list
construction) — this is what makes it a conversation rather than a series
of unrelated one-shot calls. There's no truncation/summarization of long
histories yet; that's a reasonable future addition once conversations get
long enough for it to matter (see docs/ARCHITECTURE.md).
"""
import uuid

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.knowledge.service import get_business_knowledge
from app.models.ai_usage_log import AIUsageSource
from app.models.conversation import ChatMessage, ChatRole, Conversation
from app.prompts.registry import CHAT_ASSISTANT_SYSTEM

MAX_TITLE_LENGTH = 80


class ChatError(Exception):
    """Raised for chat failures the API layer should turn into 4xx responses."""


def list_conversations(db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.organization_id == organization_id, Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(
    db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
            Conversation.user_id == user_id,
        )
        .first()
    )
    if not conversation:
        raise ChatError("Conversation not found")
    return conversation


def _make_title(first_message: str) -> str:
    stripped = first_message.strip().replace("\n", " ")
    if len(stripped) <= MAX_TITLE_LENGTH:
        return stripped
    return stripped[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


def send_message(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str,
    conversation_id: uuid.UUID | None = None,
) -> ChatMessage:
    """
    Sends a message in a conversation (creating one if conversation_id is
    None), replays full history to the provider, stores both the user's
    message and the assistant's reply, and returns the assistant's
    ChatMessage. Raises ChatError if conversation_id is given but doesn't
    belong to this org/user, or AIProviderError if the underlying call
    fails (left to propagate — see app/agents/_shared.py for why agents
    swallow this but chat doesn't: a failed chat turn should surface as a
    clear error to the person waiting on a reply, not a silent empty
    response).
    """
    if conversation_id:
        conversation = get_conversation(
            db, organization_id=organization_id, user_id=user_id, conversation_id=conversation_id
        )
    else:
        conversation = Conversation(
            organization_id=organization_id, user_id=user_id, title=_make_title(message)
        )
        db.add(conversation)
        db.flush()

    user_message = ChatMessage(conversation_id=conversation.id, role=ChatRole.USER, content=message)
    db.add(user_message)
    db.flush()

    knowledge = get_business_knowledge(db, organization_id)
    system = CHAT_ASSISTANT_SYSTEM.render_system(business_context=knowledge.render())

    history = [
        AIMessage(role=m.role.value, content=m.content)
        for m in conversation.messages  # already includes user_message, ordered by created_at
    ]

    provider = get_ai_provider_for_task(AITaskType.CHAT)

    try:
        result = generate_and_track(
            db,
            provider,
            history,
            organization_id=organization_id,
            actor_user_id=user_id,
            source=AIUsageSource.CHAT,
            system=system,
            prompt_name=CHAT_ASSISTANT_SYSTEM.name,
            prompt_version=CHAT_ASSISTANT_SYSTEM.version,
            max_tokens=1200,
        )
    except AIProviderError:
        db.commit()  # keep the user's message even though the reply failed
        raise

    assistant_message = ChatMessage(
        conversation_id=conversation.id, role=ChatRole.ASSISTANT, content=result.text
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message
