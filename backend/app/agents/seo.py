"""
SEO Agent.

Given a topic or page brief, suggests keyword ideas, identifies search
intent, writes SEO titles and meta descriptions, outlines supporting
content, and suggests hashtags. Like Ad Copy, requires a brief — SEO
suggestions with no topic to anchor to aren't actionable.
"""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents._shared import run_simple_agent
from app.ai_providers.base import AITaskType
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import SEO_SYSTEM


class SEOAgent(BaseAgent):
    name = "seo_agent"
    description = (
        "Suggests keywords, search intent, SEO titles, meta descriptions, "
        "content outlines, and hashtags for a topic or page."
    )

    def run(self, context: AgentContext, *, brief: str | None = None, **kwargs) -> AgentResult:
        if not brief or not brief.strip():
            return AgentResult(
                success=False,
                output=None,
                notes="SEO Agent needs a brief — describe the topic, page, or product "
                "you want SEO suggestions for.",
            )
        return run_simple_agent(
            context,
            prompt=SEO_SYSTEM,
            task_type=AITaskType.SEO,
            usage_source=AIUsageSource.SEO_AGENT,
            user_message=brief,
            max_tokens=1500,
        )
