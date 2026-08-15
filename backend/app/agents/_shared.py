"""
Shared helper for concrete agents.

Every agent in this app (Marketing Strategy, Audience Research, Ad Copy,
SEO) follows the same shape: read the org's business knowledge, render a
prompt, call the AI provider through the usage-tracking wrapper, and
return an AgentResult. run_simple_agent() is that shape factored out once
so each agent file only needs to supply its prompt template, task type,
and how to fold the user's brief into a user message — not reimplement
error handling or usage tracking.
"""
from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.agents.base import AgentContext, AgentResult
from app.knowledge.service import get_business_knowledge
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import PromptTemplate


def run_simple_agent(
    context: AgentContext,
    *,
    prompt: PromptTemplate,
    task_type: AITaskType,
    usage_source: AIUsageSource,
    user_message: str,
    max_tokens: int = 1500,
) -> AgentResult:
    """
    Runs the common "one-shot recommendation" agent pattern. Returns a
    failed-but-successful-call AgentResult (success=False, output=None,
    notes=<message>) on an AIProviderError, rather than letting the
    exception propagate — the API layer still gets a clean 200 with a
    "the AI call failed, here's why" body instead of needing to catch
    provider-specific exceptions itself. Programming errors (a bug in this
    function) still raise normally.
    """
    try:
        knowledge = get_business_knowledge(context.db, context.organization_id)
    except ValueError as exc:
        return AgentResult(success=False, output=None, notes=str(exc))

    system = prompt.render_system(business_context=knowledge.render())
    provider = get_ai_provider_for_task(task_type)

    try:
        result = generate_and_track(
            context.db,
            provider,
            [AIMessage(role="user", content=user_message)],
            organization_id=context.organization_id,
            actor_user_id=context.actor_user_id,
            source=usage_source,
            system=system,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            max_tokens=max_tokens,
        )
    except AIProviderError as exc:
        return AgentResult(
            success=False,
            output=None,
            notes=f"AI request failed: {exc}",
        )

    return AgentResult(
        success=True,
        output=result.text,
        requires_human_approval=False,  # recommendation-only agents never need approval to *view*
        notes=f"Generated via {result.provider}/{result.model}",
    )
