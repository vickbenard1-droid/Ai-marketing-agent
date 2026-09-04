"""
Sales agent service.

The AI narrative layer over app.leads.sales_agent_data's real numbers -
the model only ever sees real, pre-computed data; its job is to explain
and narrate, never to compute or invent a statistic of its own.
"""
import json
import uuid
from dataclasses import asdict
from datetime import date as date_type
from typing import Optional

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.knowledge.service import get_business_knowledge
from app.leads.sales_agent_data import campaigns_that_generate_buyers, find_non_converting_patterns, products_that_convert_best
from app.leads.sales_analytics import compute_sales_analytics
from app.models.ai_usage_log import AIUsageSource
from app.prompts.registry import SALES_AGENT_SYSTEM


class SalesAgentError(Exception):
    pass


class SalesAgentAnswer:
    def __init__(self, *, answer_text: str, data_used: dict):
        self.answer_text = answer_text
        self.data_used = data_used


def build_pipeline_context(db: Session, organization_id: uuid.UUID, *, date_start: date_type, date_stop: date_type) -> dict:
    analytics = compute_sales_analytics(db, organization_id, date_start=date_start, date_stop=date_stop)
    non_converting = find_non_converting_patterns(db, organization_id, date_start=date_start, date_stop=date_stop)
    campaigns = campaigns_that_generate_buyers(db, organization_id, date_start=date_start, date_stop=date_stop)
    products = products_that_convert_best(db, organization_id, date_start=date_start, date_stop=date_stop)
    return {
        "date_range": {"start": date_start.isoformat(), "stop": date_stop.isoformat()},
        "sales_analytics": asdict(analytics),
        "non_converting_patterns": [asdict(p) for p in non_converting],
        "campaigns_by_buyers": [asdict(c) for c in campaigns],
        "products_by_conversion": [asdict(p) for p in products],
    }


def ask_sales_question(db: Session, *, organization_id: uuid.UUID, actor_user_id: Optional[uuid.UUID], question: str, date_start: date_type, date_stop: date_type) -> SalesAgentAnswer:
    pipeline_data = build_pipeline_context(db, organization_id, date_start=date_start, date_stop=date_stop)
    if pipeline_data["sales_analytics"]["leads"] == 0:
        raise SalesAgentError("No leads have been recorded for this organization in the given date range — capture some leads before asking sales questions.")

    knowledge = get_business_knowledge(db, organization_id)
    system = SALES_AGENT_SYSTEM.render_system(business_context=knowledge.render(), pipeline_data_json=json.dumps(pipeline_data, indent=2, default=str), question=question)

    provider = get_ai_provider_for_task(AITaskType.SALES_AGENT)
    try:
        result = generate_and_track(
            db, provider, [AIMessage(role="user", content=question)], organization_id=organization_id, actor_user_id=actor_user_id,
            source=AIUsageSource.SALES_AGENT, system=system, prompt_name=SALES_AGENT_SYSTEM.name, prompt_version=SALES_AGENT_SYSTEM.version, max_tokens=1200,
        )
    except AIProviderError as exc:
        raise SalesAgentError(f"AI request failed: {exc}") from exc

    return SalesAgentAnswer(answer_text=result.text, data_used=pipeline_data)
