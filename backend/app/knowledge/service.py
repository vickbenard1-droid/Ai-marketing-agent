"""
Business knowledge system.

Assembles what the platform currently knows about an organization into a
single BusinessKnowledge object, and a render() method that turns it into
the plain-text "business context" block every agent prompt expects (see
app/prompts/registry.py — every system prompt has a {business_context}
placeholder filled from here).

What this reads today: Organization (name) + BusinessProfile (the Week 2
onboarding data — industry, products/services, target customers, goal,
budget, platforms). Campaigns and content are represented in the dataclass
below with empty defaults and a comment explaining why — those tables
don't exist until a later week, but the shape agents will consume is
decided now so adding the tables later doesn't change any agent's prompt
assembly, just this function's queries.

Why this is a plain-text assembler and not a vector store: the entire
"knowledge base" for one organization today is a handful of short fields
(one onboarding form's worth of data) — well under what fits directly in
a prompt, and far too small to benefit from embedding + similarity search.
RAG earns its complexity once there's a large, growing corpus per org
(many campaigns, lots of content, historical performance data) that can't
all fit in a context window. See RAG_MIGRATION_NOTES at the bottom of this
file for the seam.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.business_profile import BrandVoice, BusinessProfile
from app.models.organization import Organization


@dataclass
class CampaignSummary:
    """
    Placeholder shape for a past campaign. No Campaign table exists yet
    (see docs/ARCHITECTURE.md "not built yet"), so
    get_business_knowledge() never populates this list today — it exists
    so BusinessKnowledge.render() and every agent prompt already know how
    to describe a campaign once campaigns exist, without a second pass of
    changes through every agent.
    """

    name: str
    outcome: str  # e.g. "winning", "poor-performing", "in progress"
    summary: str


@dataclass
class ContentSummary:
    """Same rationale as CampaignSummary — no Content table exists yet."""

    title: str
    content_type: str
    summary: str


@dataclass
class BusinessKnowledge:
    business_name: str
    industry: str | None
    website_url: str | None
    products_services: str | None
    target_customers: str | None
    marketing_goal: str | None
    monthly_ad_budget: int | None
    budget_currency: str
    social_platforms: list[str] = field(default_factory=list)
    advertising_platforms: list[str] = field(default_factory=list)
    # Not populated today — see CampaignSummary/ContentSummary docstrings.
    brand_voice: str | None = None
    past_campaigns: list[CampaignSummary] = field(default_factory=list)
    past_content: list[ContentSummary] = field(default_factory=list)
    onboarding_completed: bool = False

    def render(self) -> str:
        """
        Renders as a plain-text block for direct prompt injection. Order
        matters a little (name/industry first, budget/goal last) since
        it roughly mirrors how a person would introduce their own
        business, which tends to read more naturally to the model than an
        alphabetized field dump.
        """
        lines = [f"Business name: {self.business_name}"]
        if self.industry:
            lines.append(f"Industry: {self.industry}")
        if self.website_url:
            lines.append(f"Website: {self.website_url}")
        if self.products_services:
            lines.append(f"Products/services: {self.products_services}")
        if self.target_customers:
            lines.append(f"Target customers: {self.target_customers}")
        if self.brand_voice:
            lines.append(f"Brand voice: {self.brand_voice}")
        if self.social_platforms:
            lines.append(f"Social platforms used: {', '.join(self.social_platforms)}")
        if self.advertising_platforms:
            lines.append(f"Advertising platforms used: {', '.join(self.advertising_platforms)}")
        if self.marketing_goal:
            lines.append(f"Primary marketing goal: {self.marketing_goal}")
        if self.monthly_ad_budget is not None:
            lines.append(f"Monthly advertising budget: {self.monthly_ad_budget} {self.budget_currency}")

        if self.past_campaigns:
            lines.append("\nPast campaigns:")
            for c in self.past_campaigns:
                lines.append(f"- [{c.outcome}] {c.name}: {c.summary}")
        if self.past_content:
            lines.append("\nPast content:")
            for c in self.past_content:
                lines.append(f"- [{c.content_type}] {c.title}: {c.summary}")

        if not self.onboarding_completed:
            lines.append(
                "\nNote: this business hasn't finished onboarding yet, so some "
                "of the fields above may be missing."
            )

        return "\n".join(lines)


def get_business_knowledge(db: Session, organization_id) -> BusinessKnowledge:
    """
    The single read path every agent and the chat assistant should use to
    get org context — never query Organization/BusinessProfile directly
    from agent code. Centralizing this means a later week's addition of
    campaign/content history only requires a change here, not in every
    agent.
    """
    org = db.get(Organization, organization_id)
    if not org:
        raise ValueError(f"No organization found for id {organization_id}")

    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.organization_id == organization_id)
        .first()
    )

    if not profile:
        return BusinessKnowledge(
            business_name=org.name,
            industry=None,
            website_url=None,
            products_services=None,
            target_customers=None,
            marketing_goal=None,
            monthly_ad_budget=None,
            budget_currency="USD",
            onboarding_completed=False,
        )

    return BusinessKnowledge(
        business_name=org.name,
        industry=profile.industry,
        website_url=profile.website_url,
        products_services=profile.products_services,
        target_customers=profile.target_customers,
        marketing_goal=profile.marketing_goal.value if profile.marketing_goal else None,
        monthly_ad_budget=profile.monthly_ad_budget,
        budget_currency=profile.budget_currency,
        social_platforms=profile.social_platforms or [],
        advertising_platforms=profile.advertising_platforms or [],
        onboarding_completed=profile.onboarding_completed_at is not None,
        brand_voice=_resolve_brand_voice(profile),
    )


def _resolve_brand_voice(profile: BusinessProfile) -> str | None:
    """CUSTOM resolves to the actual custom text (that's the whole point
    of Custom); any preset resolves to its plain value. See
    BrandVoice's docstring for why brand_voice_custom is ignored for
    non-Custom values even if set."""
    if profile.brand_voice is None:
        return None
    if profile.brand_voice == BrandVoice.CUSTOM:
        return profile.brand_voice_custom
    return profile.brand_voice.value


# --------------------------------------------------------------------------
# RAG migration notes
# --------------------------------------------------------------------------
# When there's enough per-organization content that it stops fitting in a
# prompt (many campaigns, a large content library, long performance
# history), the natural extension is:
#
#   1. Add a `knowledge_chunks` table: organization_id, source_type
#      (campaign/content/audience_note/...), source_id, text, embedding
#      (pgvector). One row per chunk of retrievable text.
#   2. Add an embedding step wherever campaigns/content are created —
#      write the chunk + embedding alongside the source row.
#   3. Replace get_business_knowledge()'s static "read everything" with a
#      similarity search: embed the current query/task, pull the top-N
#      relevant chunks, and either merge them into BusinessKnowledge's
#      existing fields or add a `retrieved_context: list[str]` field that
#      render() appends.
#
# The reason this is a comment and not code: nothing here needs pgvector
# or an embedding model call on every request yet, and stubbing that
# infrastructure now (with no real content to embed) would add a
# dependency and a cost with no behavior to show for it. The seam above is
# designed so that migration touches this one file, not every agent.
