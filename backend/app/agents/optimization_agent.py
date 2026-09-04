"""
Optimization Agent.

Wraps Week 9's real orchestrator.scan_organization() - runs the actual
rules engine + decision engine across every whitelisted campaign for
this org. requires_human_approval is always True at the agent-wrapper
level: even though scan_organization() may itself auto-execute a
decision for a campaign in AUTONOMOUS mode (Week 9's own, separately
gated mechanism), the orchestrator's OWN "should we run a scan right
now" step is itself presented as requiring approval by default unless
the person has explicitly set up autonomous campaigns - this agent
never silently spends anything on its own authority.
"""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.optimization.orchestrator import scan_organization


class OptimizationAgent(BaseAgent):
    name = "optimization_agent"
    description = "Scans whitelisted Meta campaigns for real, data-triggered optimization signals and generates decisions for human review."

    def run(self, context: AgentContext, **kwargs) -> AgentResult:
        results = scan_organization(context.db, context.organization_id)
        total_decisions = sum(len(r.decisions_created) for r in results)
        total_errors = sum(len(r.errors) for r in results)
        return AgentResult(
            success=True,
            output={
                "campaigns_scanned": len(results),
                "decisions_created": total_decisions,
                "decisions": [{"meta_campaign_id": r.meta_campaign_id, "decision_ids": [str(d.id) for d in r.decisions_created]} for r in results],
                "errors": total_errors,
            },
            requires_human_approval=total_decisions > 0,
            notes=f"Scanned {len(results)} whitelisted campaign(s), generated {total_decisions} decision(s) awaiting review.",
        )
