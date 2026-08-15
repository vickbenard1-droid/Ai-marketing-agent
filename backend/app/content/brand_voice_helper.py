"""
Brand voice instruction builder.

Turns a BrandVoice enum value (or an override) into the natural-language
instruction injected into content prompts' {brand_voice_instruction}
placeholder. Shared by both content_generation_service.py and
repurpose_service.py so voice guidance never drifts between the two - a
"Luxury" brand voice means the same thing whether it's shaping a single
Instagram caption or a whole repurposing batch.
"""
from app.models.business_profile import BrandVoice

_VOICE_INSTRUCTIONS: dict[BrandVoice, str] = {
    BrandVoice.PROFESSIONAL: "Professional and polished - clear, credible, no slang or excessive casualness.",
    BrandVoice.FRIENDLY: "Friendly and warm - like a helpful person talking to a friend, approachable and easygoing.",
    BrandVoice.LUXURY: "Luxury and refined - elevated language, understated confidence, no exclamation-point energy.",
    BrandVoice.EDUCATIONAL: "Educational and clear - explain the 'why,' prioritize being genuinely informative over being salesy.",
    BrandVoice.FUNNY: "Funny and light - playful, witty, doesn't take itself too seriously, but never at the expense of clarity.",
    BrandVoice.BOLD: "Bold and confident - direct, assertive statements, no hedging or apologetic language.",
    BrandVoice.INSPIRATIONAL: "Inspirational and uplifting - motivating, aspirational, focused on possibility.",
}

DEFAULT_VOICE_INSTRUCTION = (
    "No specific brand voice has been configured for this business - use a "
    "clear, professional, approachable default tone."
)


def build_brand_voice_instruction(business_brand_voice: str | None) -> str:
    """
    business_brand_voice is the already-resolved string from
    BusinessKnowledge.brand_voice (see app/knowledge/service.py) - for a
    preset it's the enum value ("luxury"); for Custom it's the business's
    own free-text description, which is used verbatim since that's the
    entire point of the Custom option.
    """
    if not business_brand_voice:
        return DEFAULT_VOICE_INSTRUCTION

    try:
        preset = BrandVoice(business_brand_voice)
    except ValueError:
        # Not a recognized preset value - this is the Custom case, where
        # business_brand_voice is the business's own free-text voice
        # description rather than an enum value at all.
        return f"Custom brand voice, as described by the business: {business_brand_voice}"

    return _VOICE_INSTRUCTIONS.get(preset, DEFAULT_VOICE_INSTRUCTION)


def build_source_material(
    *, source_text: str | None, source_url: str | None, source_asset
) -> str:
    """
    Renders the source-input fields (text, URL, uploaded asset) into the
    {source_material} block used by both the single-content generation
    prompt and the repurposing prompt — shared here rather than defined
    once per caller, since both need to describe a source the same way
    for the AI's grounding instructions to stay consistent.

    source_asset is typed loosely (not app.models.content_asset.ContentAsset
    directly) to avoid a hard import dependency from this shared-utility
    module back onto the models package; callers already have a real
    ContentAsset instance or None.
    """
    parts = []
    if source_text:
        parts.append(f"Text/product information provided:\n{source_text}")
    if source_url:
        parts.append(
            f"Reference URL: {source_url}\n"
            "(This app does not fetch or browse URLs — treat this as a reference "
            "the business gave you, not a page you've read.)"
        )
    if source_asset is not None:
        if getattr(source_asset, "ai_description", None):
            parts.append(
                f"Attached {source_asset.asset_type.value}: {source_asset.ai_description}"
            )
        else:
            parts.append(
                f"An attached {source_asset.asset_type.value} was provided but has no "
                "description available."
            )
    if not parts:
        parts.append(
            "No specific source material was provided — write general content for "
            "this business based on the business context above."
        )
    return "\n\n".join(parts)


def resolve_brand_voice_enum(brand_voice_str: str | None) -> BrandVoice | None:
    """
    knowledge.brand_voice is already-resolved text (a preset value or
    custom free text) — this recovers which enum value to stamp onto a
    Content row's brand_voice_used column. Custom free text won't match
    any preset, so it maps to BrandVoice.CUSTOM (the actual custom text
    itself lives on BusinessProfile, not duplicated per-Content-row).
    Shared by both single-content generation and repurposing, which both
    need to make this same determination for the Content rows they create.
    """
    if not brand_voice_str:
        return None
    try:
        return BrandVoice(brand_voice_str)
    except ValueError:
        return BrandVoice.CUSTOM
