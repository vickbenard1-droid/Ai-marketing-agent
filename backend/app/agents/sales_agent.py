"""
Sales Agent (orchestrator wrapper).

Wraps Week 10's real app.leads.sales_agent.ask_sales_question(). Note
the naming: app/leads/sales_agent.py is the underlying real
implementation; this file is the thin BaseAgent adapter the orchestrator
dispatches to - kept as two separate modules rather than merged, since
app/leads/sales_agent.py is also called directly from the leads API
(app/api/v1/endpoints/leads.py) independent of any orchestration.
"""
from datetime import date, timedelta

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.leads.sales_agent import SalesAgentError, ask_sales_question


class SalesAgent(BaseAgent):
    name = "sales_agent"
    description = "Analyzes real lead-to-sale pipeline data and answers sales questions, grounded only in real recorded leads and campaigns."

    def run(self, context: AgentContext, *, question: str | None = None, days: int = 30, **kwargs) -> AgentResult:
        date_stop = date.today()
        date_start = date_stop - timedelta(days=days)
        resolved_question = question or "Summarize how the sales pipeline is performing and flag any real patterns worth attention."
        try:
            answer = ask_sales_question(context.db, organization_id=context.organization_id, actor_user_id=context.actor_user_id, question=resolved_question, date_start=date_start, date_stop=date_stop)
        except SalesAgentError as exc:
            return AgentResult(success=False, output=None, notes=str(exc))
        return AgentResult(success=True, output={"answer": answer.answer_text, "data_used": answer.data_used}, requires_human_approval=False)
