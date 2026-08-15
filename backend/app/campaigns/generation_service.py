"""
Campaign generation service.

The core Week 4 AI workflow: takes an existing draft Campaign, builds a
brief from its wizard inputs plus the org's BusinessKnowledge, calls the
AI provider in JSON mode (via the prompt's own instruction — see
app/prompts/registry.py::CAMPAIGN_GENERATION_SYSTEM), and defensively
parses the result into CampaignStrategy + AdCopyVariant rows +
CreativeConcept rows.

Why a dedicated service instead of app.agents.base.BaseAgent: Week 3's
agent abstraction (see app/agents/_shared.py) assumes free-text output —
AgentResult.output is just a string a human reads. Campaign generation
needs structured, individually-editable output (the review wizard step
edits one ad copy variant's headline without touching the rest), which
free text can't give without an extra parsing layer on top of an
abstraction that wasn't designed for it. This service reuses the same
underlying pieces agents use (get_business_knowledge, generate_and_track,
the provider factory) without forcing campaign generation through
BaseAgent.run()'s single-string-output shape.

Defensive parsing: an LLM asked for JSON can still return malformed JSON,
extra prose around it, or a JSON object missing expected keys. This
module never lets a parsing failure raise an unhandled exception into the
API layer — see parse_campaign_response()'s docstring for the specific
failure modes handled.
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.ai_utils.json_extraction import extract_json_object
from app.campaigns.service import CampaignError, get_campaign
from app.knowledge.service import get_business_knowledge
from app.models.ad_copy_variant import AdCopyVariant
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_strategy import CampaignStrategy
from app.models.creative_concept import CreativeConcept, CreativeConceptType
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import CAMPAIGN_GENERATION_SYSTEM

VALID_CONCEPT_TYPES = {t.value for t in CreativeConceptType}


class CampaignGenerationError(Exception):
    """Raised when campaign generation fails — either the AI call itself,
    or the response couldn't be parsed into a usable campaign after
    defensive recovery attempts."""


def _build_campaign_brief(campaign: Campaign) -> str:
    lines = [f"Product/service: {campaign.product_name}"]
    if campaign.product_price is not None:
        lines.append(f"Price: {campaign.product_price} {campaign.budget_currency}")
    if campaign.product_description:
        lines.append(f"Product description: {campaign.product_description}")
    lines.append(f"Marketing objective: {campaign.objective.value}")
    if campaign.desired_outcome_count is not None:
        lines.append(f"Desired outcome: {campaign.desired_outcome_count} {campaign.objective.value}")
    if campaign.target_location:
        lines.append(f"Target location: {campaign.target_location}")
    if campaign.target_audience:
        lines.append(f"Target audience (as described by the business): {campaign.target_audience}")
    if campaign.existing_customer_info:
        lines.append(f"Existing customer information: {campaign.existing_customer_info}")
    if campaign.budget_amount is not None:
        lines.append(f"Budget: {campaign.budget_amount} {campaign.budget_currency}")
    if campaign.duration_days is not None:
        lines.append(f"Campaign duration: {campaign.duration_days} days")
    if campaign.landing_page_url:
        lines.append(f"Landing page: {campaign.landing_page_url}")
    return "\n".join(lines)


def generate_campaign(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    campaign_id: uuid.UUID,
) -> Campaign:
    campaign = get_campaign(db, organization_id=organization_id, campaign_id=campaign_id)
    if campaign.status == CampaignStatus.APPROVED:
        raise CampaignError("This campaign has already been approved")

    campaign.status = CampaignStatus.GENERATING
    db.commit()

    knowledge = get_business_knowledge(db, organization_id)
    system = CAMPAIGN_GENERATION_SYSTEM.render_system(
        business_context=knowledge.render(), campaign_brief=_build_campaign_brief(campaign)
    )
    provider = get_ai_provider_for_task(AITaskType.CAMPAIGN_GENERATION)

    try:
        result = generate_and_track(
            db,
            provider,
            [AIMessage(role="user", content="Generate the campaign plan as specified.")],
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            source=AIUsageSource.CAMPAIGN_BUILDER,
            system=system,
            prompt_name=CAMPAIGN_GENERATION_SYSTEM.name,
            prompt_version=CAMPAIGN_GENERATION_SYSTEM.version,
            max_tokens=4000,
        )
    except AIProviderError as exc:
        campaign.status = CampaignStatus.DRAFT  # revert — generation didn't complete
        db.commit()
        raise CampaignGenerationError(f"AI request failed: {exc}") from exc

    try:
        parsed = extract_json_object(result.text)
    except json.JSONDecodeError as exc:
        campaign.status = CampaignStatus.DRAFT
        db.commit()
        raise CampaignGenerationError(
            f"The AI response couldn't be parsed as JSON: {exc}"
        ) from exc

    _persist_generated_campaign(db, campaign, parsed)

    campaign.status = CampaignStatus.GENERATED
    campaign.generated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)
    return campaign


def _persist_generated_campaign(db: Session, campaign: Campaign, parsed: dict) -> None:
    """
    Writes parsed sections into the DB. Every access into `parsed` uses
    .get() with a sensible default rather than direct indexing — a model
    that omits a key (e.g. forgets "retargeting_strategy") should degrade
    to an empty value for that field, not crash the whole generation after
    a real, billed AI call already succeeded.
    """
    strategy_section = parsed.get("strategy") or {}
    audience_section = parsed.get("audience") or {}
    budget_section = parsed.get("budget_strategy") or {}

    existing_strategy = campaign.strategy
    if existing_strategy:
        existing_strategy.strategy_json = strategy_section
        existing_strategy.audience_json = audience_section
        existing_strategy.budget_strategy_json = budget_section
    else:
        db.add(
            CampaignStrategy(
                campaign_id=campaign.id,
                strategy_json=strategy_section,
                audience_json=audience_section,
                budget_strategy_json=budget_section,
            )
        )

    # Replace prior variants/concepts wholesale on regeneration — a
    # partial merge (keeping some old rows, adding new ones) would leave
    # stale content mixed with a fresh generation, which is more
    # confusing than a clean replace for a draft that hasn't been
    # approved yet (regeneration is blocked once approved — see
    # generate_campaign()'s status check).
    for variant in list(campaign.ad_copy_variants):
        db.delete(variant)
    for concept in list(campaign.creative_concepts):
        db.delete(concept)
    db.flush()

    for i, variant_data in enumerate(parsed.get("ad_copy_variants") or [], start=1):
        if not isinstance(variant_data, dict):
            continue
        headline = variant_data.get("headline")
        primary_text = variant_data.get("primary_text")
        cta = variant_data.get("call_to_action")
        if not headline or not primary_text or not cta:
            continue  # skip a malformed variant rather than fail the whole generation
        db.add(
            AdCopyVariant(
                campaign_id=campaign.id,
                variant_number=i,
                headline=headline[:255],
                primary_text=primary_text,
                description=(variant_data.get("description") or None),
                call_to_action=cta[:100],
            )
        )

    for concept_data in parsed.get("creative_concepts") or []:
        if not isinstance(concept_data, dict):
            continue
        concept_type = concept_data.get("concept_type")
        title = concept_data.get("title")
        description = concept_data.get("description")
        if concept_type not in VALID_CONCEPT_TYPES or not title or not description:
            continue  # skip a malformed/unknown concept rather than fail the whole generation
        db.add(
            CreativeConcept(
                campaign_id=campaign.id,
                concept_type=CreativeConceptType(concept_type),
                title=title[:255],
                description=description,
            )
        )
