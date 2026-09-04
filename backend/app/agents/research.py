"""
Research Agent.

Distinct from Audience Research (Week 3, persona-focused): this agent
answers broader market/competitive questions using the same
one-shot-recommendation pattern, since this app has no live web-search
or competitor-data source to ground a structured query against - same
honest-gap handling as every other AI feature in this app (the prompt
itself must not fabricate market data it wasn't given).
"""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents._shared import run_simple_agent
from app.ai_providers.base import AITaskType
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import MARKETING_STRATEGY_SYSTEM


class ResearchAgent(BaseAgent):
    name = "research_agent"
    description = (
        "Researches the market context for this business using only real business "
        "knowledge already on file - does not fabricate competitor or market data "
        "this app has no live source for."
    )

    def run(self, context: AgentContext, *, brief: str | None = None, **kwargs) -> AgentResult:
        user_message = brief or (
            "Given only the real business information on file, identify the most useful market "
            "research questions this business should answer before committing budget to a new "
            "goal, and note explicitly which of those questions this app cannot answer from data "
            "it has (rather than guessing at market size, competitor pricing, or similar)."
        )
        return run_simple_agent(
            context, prompt=MARKETING_STRATEGY_SYSTEM, task_type=AITaskType.MARKETING_STRATEGY,
            usage_source=AIUsageSource.MARKETING_STRATEGY_AGENT, user_message=user_message, max_tokens=1200,
        )
