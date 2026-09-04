"""
Lead follow-up service.

generate_follow_up() creates a real, grounded follow-up message for one
lead on one channel - status=DRAFTED regardless of channel (generation
and sending are separate steps). send_follow_up() only actually
delivers for EMAIL, reusing Week 1's SMTP infrastructure; every other
channel raises FollowUpChannelNotSendableError honestly rather than
faking success or silently no-oping.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.knowledge.service import get_business_knowledge
from app.mail.service import EmailContent, send_email
from app.models.ai_usage_log import AIUsageSource
from app.models.lead import Lead
from app.models.lead_follow_up import FollowUpChannel, FollowUpStatus, LeadFollowUp
from app.prompts.registry import LEAD_FOLLOW_UP_SYSTEM

_CHANNEL_TONE_DEFAULTS = {
    FollowUpChannel.EMAIL: "warm and professional",
    FollowUpChannel.WHATSAPP: "brief and conversational",
    FollowUpChannel.SMS: "very brief, one or two sentences",
    FollowUpChannel.CRM: "internal note, factual",
}


class FollowUpError(Exception):
    pass


class FollowUpChannelNotSendableError(Exception):
    pass


def _build_lead_context(lead: Lead) -> str:
    parts = [f"Name: {lead.full_name or 'Unknown'}"]
    if lead.product_interest:
        parts.append(f"Expressed interest in: {lead.product_interest}")
    parts.append(f"Current pipeline stage: {lead.stage.value}")
    if lead.notes:
        parts.append(f"Notes: {lead.notes}")
    return "\n".join(parts)


def generate_follow_up(
    db: Session, *, organization_id: uuid.UUID, lead: Lead, channel: FollowUpChannel, tone: Optional[str] = None, actor_user_id: Optional[uuid.UUID] = None
) -> LeadFollowUp:
    knowledge = get_business_knowledge(db, organization_id)
    lead_context = _build_lead_context(lead)
    resolved_tone = tone or _CHANNEL_TONE_DEFAULTS[channel]

    system = LEAD_FOLLOW_UP_SYSTEM.render_system(
        business_context=knowledge.render(), lead_context=lead_context, channel=channel.value, tone=resolved_tone
    )

    provider = get_ai_provider_for_task(AITaskType.LEAD_FOLLOW_UP)
    try:
        result = generate_and_track(
            db, provider, [AIMessage(role="user", content=f"Write a follow-up message for this lead via {channel.value}.")],
            organization_id=organization_id, actor_user_id=actor_user_id, source=AIUsageSource.LEAD_FOLLOW_UP,
            system=system, prompt_name=LEAD_FOLLOW_UP_SYSTEM.name, prompt_version=LEAD_FOLLOW_UP_SYSTEM.version, max_tokens=600,
        )
    except AIProviderError as exc:
        raise FollowUpError(f"AI request failed: {exc}") from exc

    text = result.text.strip()
    subject = None
    body = text
    if text.startswith("Subject:"):
        lines = text.split("\n", 1)
        subject = lines[0].replace("Subject:", "").strip()
        body = lines[1].strip() if len(lines) > 1 else ""

    follow_up = LeadFollowUp(organization_id=organization_id, lead_id=lead.id, channel=channel, subject=subject, body=body, status=FollowUpStatus.DRAFTED)
    db.add(follow_up)
    db.commit()
    db.refresh(follow_up)
    return follow_up


def send_follow_up(db: Session, *, follow_up: LeadFollowUp, lead: Lead) -> LeadFollowUp:
    if follow_up.channel != FollowUpChannel.EMAIL:
        raise FollowUpChannelNotSendableError(f"No live sending integration exists for the '{follow_up.channel.value}' channel yet - this is architecture only")

    if not lead.email:
        follow_up.status = FollowUpStatus.FAILED
        follow_up.send_error = "This lead has no email address on file"
        db.commit()
        db.refresh(follow_up)
        return follow_up

    try:
        send_email(EmailContent(to=lead.email, subject=follow_up.subject or "Following up", text_body=follow_up.body))
        follow_up.status = FollowUpStatus.SENT
        follow_up.sent_at = datetime.now(timezone.utc)
    except Exception as exc:
        follow_up.status = FollowUpStatus.FAILED
        follow_up.send_error = str(exc)[:500]
    db.commit()
    db.refresh(follow_up)
    return follow_up
