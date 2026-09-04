"""
Orchestrator.

The scanning pass that runs the pipeline end to end:
rules_engine.evaluate_all() -> decision_engine.generate_decision() (for
each TRIGGERED/CONCERNING signal) -> execution.process_decision(). None
of the 3 lower-level modules know about each other beyond their own
narrow interfaces; this module is the one place that wires the full
pipeline together.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

import app.optimization.decision_engine as decision_engine
import app.optimization.execution as execution
from app.analytics.metrics import compute_all
from app.analytics.service import rollup_totals
from app.models.campaign_autonomy_settings import CampaignWhitelist
from app.models.connected_account import PlatformType
from app.models.meta_campaign import MetaCampaign
from app.models.metric_snapshot import MetricEntityType
from app.optimization.rules_engine import evaluate_all


@dataclass
class CampaignScanResult:
    meta_campaign_id: str
    decisions_created: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def scan_campaign(db, *, organization_id: uuid.UUID, meta_campaign: MetaCampaign, requested_by_user_id=None) -> CampaignScanResult:
    today = date.today()
    current_start = today - timedelta(days=6)
    baseline_stop = current_start - timedelta(days=1)
    baseline_start = baseline_stop - timedelta(days=6)

    current_totals = rollup_totals(db, organization_id, source=PlatformType.META_ADS, entity_type=MetricEntityType.CAMPAIGN, entity_id=meta_campaign.id, date_start=current_start, date_stop=today)
    baseline_totals = rollup_totals(db, organization_id, source=PlatformType.META_ADS, entity_type=MetricEntityType.CAMPAIGN, entity_id=meta_campaign.id, date_start=baseline_start, date_stop=baseline_stop)
    current_derived = compute_all(current_totals)
    baseline_derived = compute_all(baseline_totals)

    signals = evaluate_all(
        current_totals=current_totals, current_derived=current_derived, baseline_totals=baseline_totals, baseline_derived=baseline_derived,
        daily_budget_cents=meta_campaign.daily_budget_cents, campaign_objective=meta_campaign.objective.value,
    )

    result = CampaignScanResult(meta_campaign_id=str(meta_campaign.id))
    for signal in signals:
        try:
            decision = decision_engine.generate_decision(db, organization_id=organization_id, meta_campaign=meta_campaign, signal=signal, actor_user_id=requested_by_user_id)
            if decision is None:
                continue
            execution.process_decision(db, organization_id=organization_id, requested_by_user_id=requested_by_user_id, decision=decision)
            result.decisions_created.append(decision)
        except Exception as exc:
            result.errors.append(f"{signal.signal_name}: decision generation failed: {exc}")
    return result


def scan_organization(db, organization_id: uuid.UUID) -> list:
    campaign_ids = {
        w.meta_campaign_id
        for w in db.query(CampaignWhitelist).filter(CampaignWhitelist.organization_id == organization_id).all()
    }
    results = []
    for campaign_id in campaign_ids:
        campaign = db.get(MetaCampaign, campaign_id)
        if not campaign:
            continue
        results.append(scan_campaign(db, organization_id=organization_id, meta_campaign=campaign))
    return results
