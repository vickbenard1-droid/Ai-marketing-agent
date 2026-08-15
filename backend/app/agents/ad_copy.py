"""
Ad Copy Agent.

Generates headlines, primary text, descriptions, CTAs, and variations for
a specific product or campaign brief. Unlike the other three agents, a
brief is required here (not optional/defaulted) — generic ad copy with no
product or campaign focus isn't a useful recommendation, so this agent
fails clearly rather than guessing what to advertise.
"""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents._shared import run_simple_agent
from app.ai_providers.base import AITaskType
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import AD_COPY_SYSTEM


class AdCopyAgent(BaseAgent):
    name = "ad_copy_agent"
    description = "Writes headlines, primary text, descriptions, CTAs, and variations for a campaign brief."

    def run(self, context: AgentContext, *, brief: str | None = None, **kwargs) -> AgentResult:
        if not brief or not brief.strip():
            return AgentResult(
                success=False,
                output=None,
                notes="Ad Copy Agent needs a brief — describe the product, offer, or "
                "campaign you want copy for.",
            )
        return run_simple_agent(
            context,
            prompt=AD_COPY_SYSTEM,
            task_type=AITaskType.AD_COPY,
            usage_source=AIUsageSource.AD_COPY_AGENT,
            user_message=brief,
            max_tokens=1500,
        )
