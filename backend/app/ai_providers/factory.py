"""
Provider factory. Agents should call get_ai_provider() or
get_ai_provider_for_task() rather than instantiating a provider class
directly — this is the single place that knows which provider is
"default" (or "right for this task") and keeps agent code
provider-agnostic.
"""
from app.ai_providers.base import AIProvider, AITaskType
from app.ai_providers.claude_provider import ClaudeProvider
from app.ai_providers.openai_provider import OpenAIProvider
from app.core.config import settings

_PROVIDERS = {
    "anthropic": ClaudeProvider,
    "openai": OpenAIProvider,
}

# Per-task provider/model overrides. Empty by default (everything uses
# DEFAULT_AI_PROVIDER's default model) — this is where a future decision
# like "use a cheaper/faster model for SEO keyword lists but the strongest
# model for full marketing strategy" would live, without touching any
# agent's code. Keyed by AITaskType so a typo fails loudly at import time
# rather than silently falling through.
TASK_PROVIDER_OVERRIDES: dict[AITaskType, tuple[str, str | None]] = {
    # AITaskType.AD_COPY: ("anthropic", "claude-haiku-4-5"),  # example override
}

# Approximate USD cost per 1M tokens, input/output. Used only for
# app.ai_usage cost estimates shown to the user/audit log — not billed
# anywhere, and deliberately conservative/approximate rather than wired to
# a live pricing API. Update when providers change pricing; a stale value
# here degrades a cost *estimate*, it doesn't affect anything functional.
MODEL_PRICING_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def get_ai_provider(name: str | None = None, model: str | None = None) -> AIProvider:
    provider_name = name or settings.DEFAULT_AI_PROVIDER
    provider_cls = _PROVIDERS.get(provider_name)
    if not provider_cls:
        raise ValueError(f"Unknown AI provider: {provider_name}")
    if model:
        return provider_cls(model=model)
    return provider_cls()


def get_ai_provider_for_task(task: AITaskType) -> AIProvider:
    """
    Resolves the provider (and optionally model) for a given task type,
    applying TASK_PROVIDER_OVERRIDES if one exists, otherwise falling back
    to the app-wide default. This is the function agents should call —
    get_ai_provider() directly is for callers that already know exactly
    which provider they want (e.g. an admin "test this provider" tool).
    """
    override = TASK_PROVIDER_OVERRIDES.get(task)
    if override:
        provider_name, model = override
        return get_ai_provider(provider_name, model)
    return get_ai_provider()


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Returns None (rather than 0.0) for an unpriced model, so callers can
    distinguish "genuinely free" from "we don't have a price for this" —
    the AI usage log stores None as NULL rather than a misleading 0.0."""
    pricing = MODEL_PRICING_PER_MILLION_TOKENS.get(model)
    if not pricing:
        return None
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
