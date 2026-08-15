"""
Content repurposing service.

Takes one source input (text, URL, and/or asset - same source-tracking
shape as generate_content, see app/content/generation_service.py) and
produces a full ContentRepurposeBatch: 5 social posts, 3 video scripts, 1
blog article, 1 email, 10 hooks - all from a single JSON-mode AI call.

Uses the same defensive JSON parsing as campaign generation (see
app/ai_utils/json_extraction.py). Individual malformed items within a
section are skipped (not the whole batch) - same principle as
app.campaigns.generation_service._persist_generated_campaign: a real,
billed AI call should degrade gracefully, not get thrown away over one
bad item.
"""
import json
import uuid

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.ai_utils.json_extraction import extract_json_object
from app.audit.service import write_audit_log
from app.content.brand_voice_helper import (
    build_brand_voice_instruction,
    build_source_material,
    resolve_brand_voice_enum,
)
from app.knowledge.service import get_business_knowledge
from app.models.ai_usage_log import AIUsageSource
from app.models.content import Content, ContentType
from app.models.content_asset import ContentAsset
from app.models.content_repurpose_batch import ContentRepurposeBatch
from app.prompts.registry import CONTENT_REPURPOSE_SYSTEM


class RepurposeError(Exception):
    """Raised when repurposing fails - the AI call itself errored, or the
    response couldn't be parsed into a usable batch."""


def repurpose_content(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    source_text: str | None = None,
    source_url: str | None = None,
    source_asset_id: uuid.UUID | None = None,
) -> ContentRepurposeBatch:
    if not source_text and not source_url and not source_asset_id:
        raise RepurposeError("Provide at least one of: source text, a URL, or an uploaded asset")

    knowledge = get_business_knowledge(db, organization_id)

    source_asset = None
    if source_asset_id:
        source_asset = (
            db.query(ContentAsset)
            .filter(ContentAsset.id == source_asset_id, ContentAsset.organization_id == organization_id)
            .first()
        )

    brand_voice_instruction = build_brand_voice_instruction(knowledge.brand_voice)
    source_material = build_source_material(
        source_text=source_text, source_url=source_url, source_asset=source_asset
    )

    system = CONTENT_REPURPOSE_SYSTEM.render_system(
        business_context=knowledge.render(),
        brand_voice_instruction=brand_voice_instruction,
        source_material=source_material,
    )
    provider = get_ai_provider_for_task(AITaskType.CONTENT_GENERATION)

    try:
        result = generate_and_track(
            db,
            provider,
            [AIMessage(role="user", content="Repurpose this content as specified.")],
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            source=AIUsageSource.CONTENT_GENERATION,
            system=system,
            prompt_name=CONTENT_REPURPOSE_SYSTEM.name,
            prompt_version=CONTENT_REPURPOSE_SYSTEM.version,
            max_tokens=4000,
        )
    except AIProviderError as exc:
        raise RepurposeError(f"AI request failed: {exc}") from exc

    try:
        parsed = extract_json_object(result.text)
    except json.JSONDecodeError as exc:
        raise RepurposeError(f"The AI response couldn't be parsed as JSON: {exc}") from exc

    batch = ContentRepurposeBatch(
        organization_id=organization_id,
        created_by_user_id=actor_user_id,
        source_text=source_text,
        source_url=source_url,
        source_asset_id=source_asset.id if source_asset else None,
    )
    db.add(batch)
    db.flush()

    brand_voice_enum = resolve_brand_voice_enum(knowledge.brand_voice)
    _persist_batch_items(
        db, batch=batch, organization_id=organization_id, brand_voice_enum=brand_voice_enum, parsed=parsed
    )

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="content.repurposed",
        resource_type="ContentRepurposeBatch",
        resource_id=str(batch.id),
        metadata={"item_count": len(batch.items)},
    )

    db.commit()
    db.refresh(batch)
    return batch


def _persist_batch_items(db: Session, *, batch, organization_id, brand_voice_enum, parsed: dict) -> None:
    def add_item(content_type: ContentType, title: str | None, body: str):
        db.add(
            Content(
                organization_id=organization_id,
                content_type=content_type,
                title=title,
                body=body,
                brand_voice_used=brand_voice_enum,
                repurpose_batch_id=batch.id,
            )
        )

    platform_map = {
        "facebook": ContentType.FACEBOOK_POST,
        "instagram": ContentType.INSTAGRAM_CAPTION,
        "linkedin": ContentType.LINKEDIN_POST,
        "x": ContentType.X_POST,
        "tiktok": ContentType.TIKTOK_CAPTION,
    }

    for post in parsed.get("social_posts") or []:
        if not isinstance(post, dict):
            continue
        text = post.get("text")
        if not text:
            continue
        content_type = platform_map.get(post.get("platform"), ContentType.FACEBOOK_POST)
        add_item(content_type, None, text)

    for script in parsed.get("video_scripts") or []:
        if not isinstance(script, dict):
            continue
        body = script.get("script")
        if not body:
            continue
        add_item(ContentType.VIDEO_SCRIPT, script.get("title"), body)

    blog = parsed.get("blog_article")
    if isinstance(blog, dict) and blog.get("body"):
        add_item(ContentType.BLOG_POST, blog.get("title"), blog["body"])

    email = parsed.get("email")
    if isinstance(email, dict) and email.get("body"):
        add_item(ContentType.EMAIL, email.get("subject"), email["body"])

    for hook in parsed.get("hooks") or []:
        if isinstance(hook, str) and hook.strip():
            add_item(ContentType.HOOK, None, hook.strip())
