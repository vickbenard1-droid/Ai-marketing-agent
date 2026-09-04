"""
Sales agent data layer.

Pure, non-AI aggregation functions - the AI never computes a statistic
itself, it only narrates statistics this module already computed.

average_lead_score_for_campaign() is also the concrete function that
lets app.optimization.orchestrator pass a real value into
app.optimization.rules_engine.evaluate_lead_quality() - the Week 9
feedback loop the spec asks for.
"""
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as date_type
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadStage
from app.models.meta_campaign import MetaCampaign


def average_lead_score_for_campaign(db: Session, *, organization_id: uuid.UUID, meta_campaign_id: uuid.UUID, date_start: date_type, date_stop: date_type) -> tuple:
    rows = db.query(Lead.score).filter(
        Lead.organization_id == organization_id, Lead.attributed_meta_campaign_id == meta_campaign_id,
        Lead.created_at >= date_start, Lead.created_at < date_type.fromordinal(date_stop.toordinal() + 1),
        Lead.score.isnot(None),
    ).all()
    scores = [r[0] for r in rows]
    if not scores:
        return None, 0
    return sum(scores) / len(scores), len(scores)


@dataclass
class NonConvertingPattern:
    stage: str
    lead_count: int
    average_score: Optional[float]
    sample_reasons: list = field(default_factory=list)


def find_non_converting_patterns(db: Session, organization_id: uuid.UUID, *, date_start: date_type, date_stop: date_type) -> list:
    _STALE_DAYS = 14
    cutoff = date_type.today().toordinal() - _STALE_DAYS
    leads = db.query(Lead).filter(
        Lead.organization_id == organization_id, Lead.created_at >= date_start,
        Lead.created_at < date_type.fromordinal(date_stop.toordinal() + 1), Lead.stage != LeadStage.WON,
    ).all()
    by_stage = defaultdict(list)
    for lead in leads:
        if lead.stage == LeadStage.LOST:
            by_stage[lead.stage.value].append(lead)
            continue
        if lead.updated_at and lead.updated_at.date().toordinal() <= cutoff:
            by_stage[lead.stage.value].append(lead)
    patterns = []
    for stage, stage_leads in by_stage.items():
        scores = [l.score for l in stage_leads if l.score is not None]
        avg_score = sum(scores) / len(scores) if scores else None
        reasons = [l.notes for l in stage_leads if l.notes][:5]
        patterns.append(NonConvertingPattern(stage=stage, lead_count=len(stage_leads), average_score=avg_score, sample_reasons=reasons))
    return sorted(patterns, key=lambda p: p.lead_count, reverse=True)


@dataclass
class CampaignConversionSummary:
    meta_campaign_id: str
    campaign_name: str
    total_leads: int
    won_leads: int
    win_rate: Optional[float]


def campaigns_that_generate_buyers(db: Session, organization_id: uuid.UUID, *, date_start: date_type, date_stop: date_type) -> list:
    rows = db.query(Lead.attributed_meta_campaign_id, MetaCampaign.name, Lead.stage, func.count(Lead.id)).join(
        MetaCampaign, MetaCampaign.id == Lead.attributed_meta_campaign_id
    ).filter(
        Lead.organization_id == organization_id, Lead.attributed_meta_campaign_id.isnot(None),
        Lead.created_at >= date_start, Lead.created_at < date_type.fromordinal(date_stop.toordinal() + 1),
    ).group_by(Lead.attributed_meta_campaign_id, MetaCampaign.name, Lead.stage).all()

    totals = defaultdict(lambda: {"name": "", "total": 0, "won": 0})
    for campaign_id, name, stage, count in rows:
        key = str(campaign_id)
        totals[key]["name"] = name
        totals[key]["total"] += count
        if stage == LeadStage.WON:
            totals[key]["won"] += count

    summaries = [
        CampaignConversionSummary(meta_campaign_id=key, campaign_name=data["name"], total_leads=data["total"], won_leads=data["won"], win_rate=(data["won"] / data["total"] * 100) if data["total"] > 0 else None)
        for key, data in totals.items()
    ]
    return sorted(summaries, key=lambda s: s.won_leads, reverse=True)


@dataclass
class ProductConversionSummary:
    product_interest: str
    total_leads: int
    won_leads: int
    win_rate: Optional[float]


def products_that_convert_best(db: Session, organization_id: uuid.UUID, *, date_start: date_type, date_stop: date_type) -> list:
    leads = db.query(Lead).filter(
        Lead.organization_id == organization_id, Lead.product_interest.isnot(None),
        Lead.created_at >= date_start, Lead.created_at < date_type.fromordinal(date_stop.toordinal() + 1),
    ).all()
    totals = defaultdict(lambda: {"total": 0, "won": 0})
    for lead in leads:
        key = lead.product_interest.strip()
        totals[key]["total"] += 1
        if lead.stage == LeadStage.WON:
            totals[key]["won"] += 1
    summaries = [
        ProductConversionSummary(product_interest=key, total_leads=data["total"], won_leads=data["won"], win_rate=(data["won"] / data["total"] * 100) if data["total"] > 0 else None)
        for key, data in totals.items()
    ]
    return sorted(summaries, key=lambda s: s.won_leads, reverse=True)
