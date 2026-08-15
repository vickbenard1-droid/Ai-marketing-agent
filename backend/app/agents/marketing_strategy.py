"""
Marketing Strategy Agent.

Understands the business, analyzes its products, defines customer
personas, identifies marketing goals, recommends channels, and develops a
marketing strategy — all as a recommendation for human review (see
app/prompts/registry.py::MARKETING_STRATEGY_SYSTEM, which instructs the
model explicitly never to claim it has taken any action).
"""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents._shared import run_simple_agent
from app.ai_providers.base import AITaskType
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import MARKETING_STRATEGY_SYSTEM


class MarketingStrategyAgent(BaseAgent):
    name = "marketing_strategy_agent"
    description = (
        "Analyzes the business and produces a marketing strategy: customer "
        "personas, goals, recommended channels, and a practical plan."
    )

    def run(self, context: AgentContext, *, brief: str | None = None, **kwargs) -> AgentResult:
        user_message = (
            brief
            or "Produce a complete marketing strategy for this business: analyze "
            "the products/services, define 2-3 customer personas, confirm or refine "
            "the marketing goal, recommend the channels worth pursuing first, and "
            "lay out a practical strategy for the next 90 days."
        )
        return run_simple_agent(
            context,
            prompt=MARKETING_STRATEGY_SYSTEM,
            task_type=AITaskType.MARKETING_STRATEGY,
            usage_source=AIUsageSource.MARKETING_STRATEGY_AGENT,
            user_message=user_message,
            max_tokens=2000,
        )
