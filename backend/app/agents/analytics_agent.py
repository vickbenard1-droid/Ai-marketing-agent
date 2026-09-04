"""
Analytics Agent.

Wraps real Week 8 rollup/derived-metric functions - the orchestrator
step "Analyze historical performance" calls this to get real numbers,
not an AI-generated summary. This agent's output IS the real data;
narration over it (if wanted) is a separate concern the caller can layer
on, same "AI narrates, never computes" discipline used throughout this
app.
"""
from dataclasses import asdict
from datetime import date, timedelta

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.analytics.metrics import compute_all
from app.analytics.service import rollup_totals


class AnalyticsAgent(BaseAgent):
    name = "analytics_agent"
    description = "Returns real, computed performance totals and derived metrics for this organization over a recent window."

    def run(self, context: AgentContext, *, days: int = 30, **kwargs) -> AgentResult:
        date_stop = date.today()
        date_start = date_stop - timedelta(days=days)
        totals = rollup_totals(context.db, context.organization_id, date_start=date_start, date_stop=date_stop)
        derived = compute_all(totals)
        return AgentResult(
            success=True,
            output={"date_range": {"start": date_start.isoformat(), "stop": date_stop.isoformat()}, "raw": asdict(totals), "derived": asdict(derived)},
            requires_human_approval=False,
            notes="Real, computed data - no AI narration applied.",
        )
