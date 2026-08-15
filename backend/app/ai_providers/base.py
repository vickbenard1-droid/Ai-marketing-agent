"""
AI provider abstraction.

Every agent (Marketing Strategy, Ad Copy, SEO, Audience Research) calls an
AIProvider instance rather than the Claude or OpenAI SDKs directly. This is
what lets us support both providers — and add more later — without touching
agent logic.
"""
import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Union


@dataclass
class ImageContentBlock:
    """
    A base64-encoded image to send alongside text in a message — used by
    the Week 5 content engine to let the AI actually see an uploaded
    product photo (see app/content/generation_service.py), not just a
    text description of one. media_type must be one the target provider
    accepts (image/jpeg, image/png, image/gif, image/webp for both
    Anthropic and OpenAI's current vision-capable models).
    """

    data_base64: str
    media_type: str


@dataclass
class AIMessage:
    role: str  # "user" | "assistant" | "system"
    # Plain text is the common case (every agent, chat, and campaign
    # generation call uses this). A list of blocks is only used when
    # sending an image alongside text — see ImageContentBlock. Providers
    # are responsible for translating this into their own wire format
    # (see ClaudeProvider._to_provider_content / OpenAIProvider's
    # equivalent).
    content: Union[str, list[Union[str, ImageContentBlock]]]


@dataclass
class TokenUsage:
    """
    Normalized token usage, regardless of provider. Anthropic calls these
    input_tokens/output_tokens; OpenAI calls them prompt_tokens/
    completion_tokens — both map onto this shape so cost tracking
    (app/ai_usage/service.py) never needs to know which provider produced
    a given AICompletionResult.
    """

    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class AICompletionResult:
    text: str
    provider: str
    model: str
    usage: TokenUsage
    raw: dict | None = None


class AIProviderError(Exception):
    """Base class for all AI provider failures. Callers (agents, chat)
    should catch this rather than httpx/SDK-specific exceptions, so
    swapping the underlying HTTP client never ripples into agent code."""


class AIProviderAuthError(AIProviderError):
    """API key missing, invalid, or rejected by the provider."""


class AIProviderRateLimitError(AIProviderError):
    """Provider returned a rate-limit response (HTTP 429)."""


class AIProviderTimeoutError(AIProviderError):
    """Request to the provider timed out."""


class AIProviderResponseError(AIProviderError):
    """Provider returned an unexpected or malformed response (e.g. 5xx,
    or a 200 whose body doesn't have the shape we expect)."""


class AITaskType(str, enum.Enum):
    """
    Task categories used for per-task provider/model selection (see
    app/ai_providers/factory.py::get_ai_provider_for_task). Keeping this
    as a small closed set — rather than a free-form string — means a typo
    in a task name fails at call time with a clear error instead of
    silently falling back to the default provider.
    """

    MARKETING_STRATEGY = "marketing_strategy"
    AUDIENCE_RESEARCH = "audience_research"
    AD_COPY = "ad_copy"
    SEO = "seo"
    CHAT = "chat"
    CAMPAIGN_GENERATION = "campaign_generation"
    CONTENT_GENERATION = "content_generation"
    IMAGE_ANALYSIS = "image_analysis"
    POSTING_RECOMMENDATION = "posting_recommendation"


class AIProvider(ABC):
    """Common interface all AI providers must implement."""

    name: str

    @abstractmethod
    def generate(
        self,
        messages: list[AIMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AICompletionResult:
        """
        Send messages to the provider and return a normalized result.

        Raises an AIProviderError subclass on failure — never lets a raw
        httpx/SDK exception escape, so callers only need to handle one
        exception hierarchy regardless of provider.
        """
        raise NotImplementedError
