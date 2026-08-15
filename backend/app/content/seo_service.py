"""
SEO generation service.

Produces a structured SEOContent row from a topic (and, optionally, a
linked Content row it's optimizing for). JSON mode, same defensive
parsing as campaign generation and repurposing (see
app/ai_utils/json_extraction.py).

The spec's "do not invent search-volume statistics without a verified
data source" constraint is enforced at three levels, deliberately
redundant: (1) the prompt instructs the model never to include one (see
app/prompts/registry.py::SEO_STRUCTURED_SYSTEM), (2) the SEOContent model
has no column to put one in even if the model ignored the instruction
(see that model's own docstring), and (3) _persist_seo_result below only
ever copies the specific named fields the JSON schema defines - an extra
"search_volume" key in a rogue response would simply be ignored, not
stored, because nothing here does a generic dict-to-model field copy.
"""
import json
import uuid

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.ai_utils.json_extraction import extract_json_object
from app.audit.service import write_audit_log
from app.knowledge.service import get_business_knowledge
from app.models.ai_usage_log import AIUsageSource
from app.models.content import Content
from app.models.seo_content import SEOContent
from app.prompts.registry import SEO_STRUCTURED_SYSTEM


class SEOGenerationError(Exception):
    """Raised when SEO generation fails - the AI call itself errored, or
    the response couldn't be parsed into usable SEO fields."""


def generate_seo(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    topic: str,
    content_id: uuid.UUID | None = None,
) -> SEOContent:
    linked_content = None
    if content_id:
        linked_content = (
            db.query(Content)
            .filter(Content.id == content_id, Content.organization_id == organization_id)
            .first()
        )
        if not linked_content:
            raise SEOGenerationError("The linked content item was not found in this organization")

    knowledge = get_business_knowledge(db, organization_id)
    system = SEO_STRUCTURED_SYSTEM.render_system(business_context=knowledge.render(), topic=topic)
    provider = get_ai_provider_for_task(AITaskType.SEO)

    try:
        result = generate_and_track(
            db,
            provider,
            [AIMessage(role="user", content="Generate the SEO analysis as specified.")],
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            source=AIUsageSource.SEO_AGENT,
            system=system,
            prompt_name=SEO_STRUCTURED_SYSTEM.name,
            prompt_version=SEO_STRUCTURED_SYSTEM.version,
            max_tokens=1500,
        )
    except AIProviderError as exc:
        raise SEOGenerationError(f"AI request failed: {exc}") from exc

    try:
        parsed = extract_json_object(result.text)
    except json.JSONDecodeError as exc:
        raise SEOGenerationError(f"The AI response couldn't be parsed as JSON: {exc}") from exc

    seo = _persist_seo_result(
        db,
        organization_id=organization_id,
        topic=topic,
        content_id=linked_content.id if linked_content else None,
        parsed=parsed,
    )

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="seo.generated",
        resource_type="SEOContent",
        resource_id=str(seo.id),
        metadata={"topic": topic},
    )

    db.commit()
    db.refresh(seo)
    return seo


def _clean_str_list(value) -> list[str] | None:
    if not isinstance(value, list):
        return None
    cleaned = [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return cleaned or None


def _persist_seo_result(
    db: Session, *, organization_id: uuid.UUID, topic: str, content_id: uuid.UUID | None, parsed: dict
) -> SEOContent:
    """
    Only copies the named fields from `parsed` - see module docstring for
    why this (not a generic dict merge) is part of how the
    never-invent-search-volume constraint is enforced. If content_id is
    given and an SEOContent row already exists for it (one-to-one, see
    SEOContent.content_id's unique constraint), updates that row in place
    rather than violating the constraint with a second insert.
    """
    existing = None
    if content_id:
        existing = db.query(SEOContent).filter(SEOContent.content_id == content_id).first()

    seo = existing or SEOContent(organization_id=organization_id, content_id=content_id, topic=topic)
    seo.topic = topic
    seo.primary_keyword = parsed.get("primary_keyword")
    seo.secondary_keywords = _clean_str_list(parsed.get("secondary_keywords"))
    seo.search_intent = parsed.get("search_intent")
    seo.seo_title = parsed.get("seo_title")
    seo.meta_description = parsed.get("meta_description")
    seo.url_slug = parsed.get("url_slug")
    seo.h1 = parsed.get("h1")
    seo.h2_structure = _clean_str_list(parsed.get("h2_structure"))
    seo.internal_linking_suggestions = _clean_str_list(parsed.get("internal_linking_suggestions"))
    seo.image_alt_text = parsed.get("image_alt_text")
    seo.hashtags = _clean_str_list(parsed.get("hashtags"))

    if not existing:
        db.add(seo)
    db.flush()
    return seo
