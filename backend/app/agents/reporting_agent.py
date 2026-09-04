"""
Reporting Agent.

The one genuinely new agent this week - no prior week built a
reporting/summarization module. Deliberately pulls from real Week 8
analytics + Week 10 sales data (the same functions AnalyticsAgent/
SalesAgent already call) rather than inventing a parallel data source,
and generates a plain-language summary via the standard one-shot AI
pattern, grounded explicitly in the real numbers assembled first.
"""
import json
from dataclasses import asdict
from datetime import date, timedelta

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.analytics.metrics import compute_all
from app.analytics.service import rollup_totals
from app.knowledge.service import get_business_knowledge
from app.leads.sales_analytics import compute_sales_analytics
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import SALES_AGENT_SYSTEM


class ReportingAgent(BaseAgent):
    name = "reporting_agent"
    description = "Assembles a plain-language performance report from real, already-computed analytics and sales data."

    def run(self, context: AgentContext, *, days: int = 30, **kwargs) -> AgentResult:
        date_stop = date.today()
        date_start = date_stop - timedelta(days=days)

        totals = rollup_totals(context.db, context.organization_id, date_start=date_start, date_stop=date_stop)
        derived = compute_all(totals)
        sales = compute_sales_analytics(context.db, context.organization_id, date_start=date_start, date_stop=date_stop)

        report_data = {"date_range": {"start": date_start.isoformat(), "stop": date_stop.isoformat()}, "performance": {"raw": asdict(totals), "derived": asdict(derived)}, "sales": asdict(sales)}

        knowledge = get_business_knowledge(context.db, context.organization_id)
        # Reuses SALES_AGENT_SYSTEM's own real-data-only discipline rather than
        # writing a near-duplicate prompt just for this agent.
        system = SALES_AGENT_SYSTEM.render_system(business_context=knowledge.render(), pipeline_data_json=json.dumps(report_data, indent=2, default=str), question="Write a plain-language performance report summarizing this period.")

        provider = get_ai_provider_for_task(AITaskType.SALES_AGENT)
        try:
            result = generate_and_track(context.db, provider, [AIMessage(role="user", content="Write a plain-language performance report for this period.")], organization_id=context.organization_id, actor_user_id=context.actor_user_id, source=AIUsageSource.SALES_AGENT, system=system, prompt_name=SALES_AGENT_SYSTEM.name, prompt_version=SALES_AGENT_SYSTEM.version, max_tokens=1200)
        except AIProviderError as exc:
            return AgentResult(success=True, output={"data": report_data, "narrative": None}, notes=f"Real data assembled; narrative generation failed: {exc}")

        return AgentResult(success=True, output={"data": report_data, "narrative": result.text}, requires_human_approval=False)
