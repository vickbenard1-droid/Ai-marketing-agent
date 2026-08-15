"""
Content generation service.

Generates one Content row from text/product-info/URL/asset input,
grounded in the org's BusinessKnowledge (including brand voice - see
app/content/brand_voice_helper.py) and, when a source asset is given, its
AI-generated image description (see app/content/asset_service.py).

Unlike campaign generation, this is NOT JSON mode - most content types are
a single block of text (a caption, a post, a product description), so the
prompt asks for exactly that and the response is stored as-is.
"""
import uuid

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.audit.service import write_audit_log
from app.content.brand_voice_helper import (
    build_brand_voice_instruction,
    build_source_material,
    resolve_brand_voice_enum,
)
from app.content.content_types import get_content_type_metadata
from app.knowledge.service import get_business_knowledge
from app.models.ai_usage_log import AIUsageSource
from app.models.content import Content, ContentType
from app.models.content_asset import ContentAsset
from app.prompts.registry import CONTENT_GENERATION_SYSTEM


class ContentGenerationError(Exception):
    """Raised when content generation fails - the AI call itself errored.
    No JSON parsing failure mode here (see module docstring)."""


def generate_content(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    content_type: ContentType,
    source_text: str | None = None,
    source_url: str | None = None,
    source_asset_id: uuid.UUID | None = None,
) -> Content:
    knowledge = get_business_knowledge(db, organization_id)

    source_asset = None
    if source_asset_id:
        source_asset = (
            db.query(ContentAsset)
            .filter(ContentAsset.id == source_asset_id, ContentAsset.organization_id == organization_id)
            .first()
        )

    metadata = get_content_type_metadata(content_type)
    brand_voice_instruction = build_brand_voice_instruction(knowledge.brand_voice)
    source_material = build_source_material(
        source_text=source_text, source_url=source_url, source_asset=source_asset
    )

    system = CONTENT_GENERATION_SYSTEM.render_system(
        business_context=knowledge.render(),
        content_type_label=metadata["label"],
        format_guidance=metadata["format_guidance"],
        brand_voice_instruction=brand_voice_instruction,
        source_material=source_material,
    )

    provider = get_ai_provider_for_task(AITaskType.CONTENT_GENERATION)

    try:
        result = generate_and_track(
            db,
            provider,
            [AIMessage(role="user", content=f"Write the {metadata['label']} now.")],
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            source=AIUsageSource.CONTENT_GENERATION,
            system=system,
            prompt_name=CONTENT_GENERATION_SYSTEM.name,
            prompt_version=CONTENT_GENERATION_SYSTEM.version,
            max_tokens=1800,
        )
    except AIProviderError as exc:
        raise ContentGenerationError(f"AI request failed: {exc}") from exc

    content = Content(
        organization_id=organization_id,
        created_by_user_id=actor_user_id,
        content_type=content_type,
        body=result.text.strip(),
        source_text=source_text,
        source_url=source_url,
        source_asset_id=source_asset.id if source_asset else None,
        brand_voice_used=resolve_brand_voice_enum(knowledge.brand_voice),
    )
    db.add(content)
    db.flush()

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="content.generated",
        resource_type="Content",
        resource_id=str(content.id),
        metadata={"content_type": content_type.value},
    )

    db.commit()
    db.refresh(content)
    return content
