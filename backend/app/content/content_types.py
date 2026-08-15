"""
Content type metadata.

Maps each ContentType to a human-readable label and format guidance
string injected into the content generation prompt (see
app/prompts/registry.py::CONTENT_GENERATION_SYSTEM's {format_guidance}
placeholder). Kept as data here rather than inline in the service so the
platform conventions (character limits, structure expectations) are easy
to review and adjust in one place as platforms change their norms.
"""
from app.models.content import ContentType

CONTENT_TYPE_METADATA: dict[ContentType, dict[str, str]] = {
    ContentType.FACEBOOK_POST: {
        "label": "Facebook post",
        "format_guidance": (
            "40-80 words works best for engagement. Conversational tone, can include "
            "emoji. End with a question or clear next step where natural."
        ),
    },
    ContentType.INSTAGRAM_CAPTION: {
        "label": "Instagram caption",
        "format_guidance": (
            "Up to 2,200 characters allowed, but lead with the strongest line since "
            "it's the only part visible before 'more.' Casual, visual language. "
            "Emoji are welcome. Do not include hashtags in the caption body itself — "
            "those are generated separately by the SEO agent."
        ),
    },
    ContentType.LINKEDIN_POST: {
        "label": "LinkedIn post",
        "format_guidance": (
            "150-300 words. Professional but not stiff — first-person or company "
            "voice, focused on business value, insight, or a genuine story. Avoid "
            "excessive emoji or hard-sell language."
        ),
    },
    ContentType.X_POST: {
        "label": "X (Twitter) post",
        "format_guidance": "Under 280 characters, including spaces. Punchy, single idea.",
    },
    ContentType.TIKTOK_CAPTION: {
        "label": "TikTok caption",
        "format_guidance": (
            "Short — 1-2 sentences, under 150 characters. High-energy, casual, "
            "written to accompany a video, not stand alone."
        ),
    },
    ContentType.YOUTUBE_TITLE: {
        "label": "YouTube video title",
        "format_guidance": "Under 70 characters. Front-load the key benefit or hook; avoid clickbait that isn't backed by the content.",
    },
    ContentType.YOUTUBE_DESCRIPTION: {
        "label": "YouTube video description",
        "format_guidance": (
            "First 1-2 sentences must work standalone (shown before 'more'). "
            "150-300 words total, can include a brief structured summary of what's covered."
        ),
    },
    ContentType.BLOG_POST: {
        "label": "Blog post",
        "format_guidance": (
            "600-900 words. Include a clear title, an introduction, 3-5 subsections "
            "with implied headings (mark them clearly), and a conclusion. "
            "Write in complete, well-structured prose."
        ),
    },
    ContentType.PRODUCT_DESCRIPTION: {
        "label": "Product description",
        "format_guidance": (
            "100-200 words. Lead with the core benefit, cover key features "
            "concretely, end with what makes this the right choice."
        ),
    },
    ContentType.EMAIL: {
        "label": "Marketing email",
        "format_guidance": (
            "Provide a subject line (under 50 characters) and a body (150-300 words). "
            "Label them clearly as 'Subject:' and 'Body:'. Body should have a clear "
            "single call to action."
        ),
    },
}


def get_content_type_metadata(content_type: ContentType) -> dict[str, str]:
    return CONTENT_TYPE_METADATA.get(
        content_type,
        {
            "label": content_type.value.replace("_", " "),
            "format_guidance": "Standard format for this content type.",
        },
    )
