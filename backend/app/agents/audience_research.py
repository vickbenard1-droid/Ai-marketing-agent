"""
Audience Research Agent.

Defines target audiences, generates audience segments, identifies
customer pain points and buying motivations, and recommends targeting
approaches — as a recommendation for human review.
"""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents._shared import run_simple_agent
from app.ai_providers.base import AITaskType
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import AUDIENCE_RESEARCH_SYSTEM


class AudienceResearchAgent(BaseAgent):
    name = "audience_research_agent"
    description = (
        "Defines target audience segments, their pain points, buying "
        "motivations, and how to target each one."
    )

    def run(self, context: AgentContext, *, brief: str | None = None, **kwargs) -> AgentResult:
        user_message = (
            brief
            or "Define this business's target audience: identify 2-4 distinct "
            "audience segments, each with their pain points, buying motivations, "
            "and a recommended targeting approach."
        )
        return run_simple_agent(
            context,
            prompt=AUDIENCE_RESEARCH_SYSTEM,
            task_type=AITaskType.AUDIENCE_RESEARCH,
            usage_source=AIUsageSource.AUDIENCE_RESEARCH_AGENT,
            user_message=user_message,
            max_tokens=2000,
        )
