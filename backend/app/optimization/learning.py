"""
Learning module.

The spec's "Track: AI recommendation, Action taken, Result" loop.
record_outcome() compares a real "before" rollup against a real "after"
rollup for an executed decision - genuinely measured, never estimated.

HONEST LIMITATION: this comparison cannot isolate causation. outcome_json
always carries an explicit correlation_only field - no function here
ever computes or claims a "this action worked" verdict.
"""
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.analytics.metrics import compute_all
from app.analytics.service import rollup_totals
from app.models.connected_account import PlatformType
from app.models.metric_snapshot import MetricEntityType
from app.models.optimization_decision import DecisionStatus, OptimizationDecision

_MIN_OBSERVATION_WINDOW_DAYS = 3


def _can_record_outcome(decision: OptimizationDecision) -> bool:
    if decision.status != DecisionStatus.EXECUTED:
        return False
    if decision.outcome_json is not None:
        return False
    if decision.updated_at is None:
        return False
    updated_at = decision.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    days_since_execution = (datetime.now(timezone.utc) - updated_at).days
    return days_since_execution >= _MIN_OBSERVATION_WINDOW_DAYS


def record_outcome(db: Session, decision: OptimizationDecision) -> Optional[OptimizationDecision]:
    if not _can_record_outcome(decision):
        return None

    execution_date = decision.updated_at.date()
    after_start = execution_date + timedelta(days=1)
    after_stop = date.today()
    if after_start > after_stop:
        return None

    before_stop = execution_date - timedelta(days=1)
    before_start = before_stop - timedelta(days=_MIN_OBSERVATION_WINDOW_DAYS - 1)

    before_totals = rollup_totals(db, decision.organization_id, source=PlatformType.META_ADS, entity_type=MetricEntityType.CAMPAIGN, entity_id=decision.meta_campaign_id, date_start=before_start, date_stop=before_stop)
    after_totals = rollup_totals(db, decision.organization_id, source=PlatformType.META_ADS, entity_type=MetricEntityType.CAMPAIGN, entity_id=decision.meta_campaign_id, date_start=after_start, date_stop=after_stop)
    before_derived = compute_all(before_totals)
    after_derived = compute_all(after_totals)

    decision.outcome_json = {
        "before_period": {"start": before_start.isoformat(), "stop": before_stop.isoformat(), "raw": asdict(before_totals), "derived": asdict(before_derived)},
        "after_period": {"start": after_start.isoformat(), "stop": after_stop.isoformat(), "raw": asdict(after_totals), "derived": asdict(after_derived)},
        "correlation_only": "This compares real measured performance before and after the action - it does NOT establish that this action caused any change observed.",
    }
    decision.outcome_recorded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(decision)
    return decision


def find_decisions_ready_for_outcome(db: Session, organization_id: uuid.UUID) -> list:
    candidates = (
        db.query(OptimizationDecision)
        .filter(OptimizationDecision.organization_id == organization_id, OptimizationDecision.status == DecisionStatus.EXECUTED, OptimizationDecision.outcome_json.is_(None))
        .all()
    )
    return [d for d in candidates if _can_record_outcome(d)]
