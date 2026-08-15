"""
AI posting recommendation service.

Generates a prediction (never a guarantee - see the prompt's own
enforcement of this) for when/where/how to post a given ScheduledPost's
content, and writes it into that post's ai_recommended_* columns - never
into scheduled_for or any field that actually drives publishing. See
app/models/scheduled_post.py's module docstring and
app/scheduling/service.py::accept_ai_recommendation for the full
separation-of-prediction-from-decision design this is one half of.

JSON mode, same defensive parsing as campaign/repurpose/SEO generation.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.ai_utils.json_extraction import extract_json_object
from app.knowledge.service import get_business_knowledge
from app.models.ai_usage_log import AIUsageSource
from app.models.connected_account import ConnectedAccount, ConnectionStatus
from app.models.scheduled_post import ScheduledPost
from app.prompts.registry import POSTING_RECOMMENDATION_SYSTEM


class RecommendationError(Exception):
    """Raised when generating a posting recommendation fails."""


def _clean_str_list(value) -> list[str] | None:
    if not isinstance(value, list):
        return None
    cleaned = [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return cleaned or None


def generate_posting_recommendation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    scheduled_post_id: uuid.UUID,
) -> ScheduledPost:
    post = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.id == scheduled_post_id, ScheduledPost.organization_id == organization_id)
        .first()
    )
    if not post:
        raise RecommendationError("Scheduled post not found")

    available_platforms = [
        acc.platform.value
        for acc in db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.organization_id == organization_id,
            ConnectedAccount.status == ConnectionStatus.CONNECTED,
        )
        .all()
    ]
    if not available_platforms:
        raise RecommendationError("No connected social accounts to recommend a platform from")

    knowledge = get_business_knowledge(db, organization_id)
    system = POSTING_RECOMMENDATION_SYSTEM.render_system(
        business_context=knowledge.render(),
        content_body=post.content.body,
        content_type=post.content.content_type.value,
        available_platforms=", ".join(available_platforms),
    )
    provider = get_ai_provider_for_task(AITaskType.POSTING_RECOMMENDATION)

    try:
        result = generate_and_track(
            db,
            provider,
            [AIMessage(role="user", content="Generate the posting recommendation as specified.")],
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            source=AIUsageSource.POSTING_RECOMMENDATION,
            system=system,
            prompt_name=POSTING_RECOMMENDATION_SYSTEM.name,
            prompt_version=POSTING_RECOMMENDATION_SYSTEM.version,
            max_tokens=800,
        )
    except AIProviderError as exc:
        raise RecommendationError(f"AI request failed: {exc}") from exc

    try:
        parsed = extract_json_object(result.text)
    except json.JSONDecodeError as exc:
        raise RecommendationError(f"The AI response couldn't be parsed as JSON: {exc}") from exc

    # recommended_post_time is deliberately a day/time DESCRIPTION in the
    # prompt's own words (see POSTING_RECOMMENDATION_SYSTEM), not a
    # parseable timestamp - this app has no real per-audience analytics
    # to compute a specific instant from. Storing it as an actual
    # datetime on ai_recommended_post_time (a DateTime column) requires
    # picking *some* concrete instant, so this resolves the description
    # to "the next occurrence of a reasonable default hour" rather than
    # attempting to parse arbitrary natural language into a timestamp,
    # which would be a much larger and more fragile undertaking. The
    # human-readable description itself is preserved in full in
    # ai_recommendation_rationale so nothing is lost - a person reviewing
    # the recommendation sees the real reasoning, not just a bare time.
    recommended_dt = _next_default_slot()

    post.ai_recommended_post_time = recommended_dt
    post.ai_recommended_platform = parsed.get("recommended_platform")
    post.ai_recommended_format = parsed.get("recommended_format")
    post.ai_recommended_hashtags = _clean_str_list(parsed.get("recommended_hashtags"))
    rationale_parts = []
    if parsed.get("recommended_post_time"):
        rationale_parts.append(f"Suggested time: {parsed['recommended_post_time']}.")
    if parsed.get("rationale"):
        rationale_parts.append(parsed["rationale"])
    post.ai_recommendation_rationale = " ".join(rationale_parts) or None

    db.commit()
    db.refresh(post)
    return post


def _next_default_slot() -> datetime:
    """A placeholder concrete instant (tomorrow at 18:00 UTC) for
    ai_recommended_post_time's DateTime column - see the comment above
    for why the prompt's own time description, not this value, is the
    actual human-readable recommendation. Accepting this recommendation
    (app.scheduling.service.accept_ai_recommendation) schedules for this
    slot; a person who wants the AI's actual described time (e.g.
    "Wednesday evening") rather than this generic default should set
    scheduled_for manually instead."""
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    return tomorrow.replace(hour=18, minute=0, second=0, microsecond=0)
