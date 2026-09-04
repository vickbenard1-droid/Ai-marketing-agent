"""
Rules engine.

Evaluates the spec's 11 optimization signals against real
app.analytics.service.rollup_totals()/app.analytics.metrics.compute_all()
data - the same Week 8 foundation the dashboards use.

HONEST GAP: this app has real data for 9 of the 11 signals. Frequency
(Meta's average-impressions-per-user metric) was never requested/stored
in Week 7's sync. Lead quality has no data source at all this week -
both are evaluated by dedicated functions that always return
UNAVAILABLE, explicitly, rather than fabricated from unrelated data.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.analytics.metrics import DerivedMetrics, RawTotals


class SignalStatus(str, Enum):
    NORMAL = "normal"
    CONCERNING = "concerning"
    TRIGGERED = "triggered"
    UNAVAILABLE = "unavailable"


@dataclass
class SignalEvaluation:
    signal_name: str
    status: SignalStatus
    detail: str
    value: Optional[float] = None
    baseline_value: Optional[float] = None


def evaluate_ctr(current: DerivedMetrics, baseline: Optional[DerivedMetrics]) -> SignalEvaluation:
    if current.ctr is None:
        return SignalEvaluation("CTR", SignalStatus.UNAVAILABLE, "No impressions/clicks data")
    if baseline is None or baseline.ctr is None:
        return SignalEvaluation("CTR", SignalStatus.NORMAL, f"CTR is {current.ctr:.2f}% (no baseline)", value=current.ctr)
    drop = ((baseline.ctr - current.ctr) / baseline.ctr) * 100 if baseline.ctr > 0 else 0
    if drop >= 30:
        return SignalEvaluation("CTR", SignalStatus.TRIGGERED, f"CTR dropped {drop:.1f}%", value=current.ctr, baseline_value=baseline.ctr)
    if drop >= 15:
        return SignalEvaluation("CTR", SignalStatus.CONCERNING, f"CTR dropped {drop:.1f}%", value=current.ctr, baseline_value=baseline.ctr)
    return SignalEvaluation("CTR", SignalStatus.NORMAL, f"CTR is {current.ctr:.2f}%, stable", value=current.ctr, baseline_value=baseline.ctr)


def evaluate_cpc(current: DerivedMetrics, baseline: Optional[DerivedMetrics]) -> SignalEvaluation:
    if current.cpc_cents is None:
        return SignalEvaluation("CPC", SignalStatus.UNAVAILABLE, "No click data")
    if baseline is None or not baseline.cpc_cents:
        return SignalEvaluation("CPC", SignalStatus.NORMAL, f"CPC is ${current.cpc_cents/100:.2f}", value=current.cpc_cents)
    inc = ((current.cpc_cents - baseline.cpc_cents) / baseline.cpc_cents) * 100
    if inc >= 50:
        return SignalEvaluation("CPC", SignalStatus.TRIGGERED, f"CPC increased {inc:.1f}%", value=current.cpc_cents, baseline_value=baseline.cpc_cents)
    if inc >= 25:
        return SignalEvaluation("CPC", SignalStatus.CONCERNING, f"CPC increased {inc:.1f}%", value=current.cpc_cents, baseline_value=baseline.cpc_cents)
    return SignalEvaluation("CPC", SignalStatus.NORMAL, f"CPC is ${current.cpc_cents/100:.2f}, stable", value=current.cpc_cents, baseline_value=baseline.cpc_cents)


def evaluate_cpm(current: DerivedMetrics, baseline: Optional[DerivedMetrics]) -> SignalEvaluation:
    if current.cpm_cents is None:
        return SignalEvaluation("CPM", SignalStatus.UNAVAILABLE, "No impression data")
    if baseline is None or not baseline.cpm_cents:
        return SignalEvaluation("CPM", SignalStatus.NORMAL, f"CPM is ${current.cpm_cents/100:.2f}", value=current.cpm_cents)
    inc = ((current.cpm_cents - baseline.cpm_cents) / baseline.cpm_cents) * 100
    if inc >= 40:
        return SignalEvaluation("CPM", SignalStatus.CONCERNING, f"CPM increased {inc:.1f}% (rising auction cost)", value=current.cpm_cents, baseline_value=baseline.cpm_cents)
    return SignalEvaluation("CPM", SignalStatus.NORMAL, f"CPM is ${current.cpm_cents/100:.2f}, stable", value=current.cpm_cents, baseline_value=baseline.cpm_cents)


def evaluate_cpa(current: DerivedMetrics, baseline: Optional[DerivedMetrics]) -> SignalEvaluation:
    if current.cpa_cents is None:
        return SignalEvaluation("CPA", SignalStatus.UNAVAILABLE, "No purchase data")
    if baseline is None or baseline.cpa_cents is None:
        return SignalEvaluation("CPA", SignalStatus.NORMAL, f"CPA is ${current.cpa_cents/100:.2f}", value=current.cpa_cents)
    inc = ((current.cpa_cents - baseline.cpa_cents) / baseline.cpa_cents) * 100 if baseline.cpa_cents > 0 else 0
    if inc >= 50:
        return SignalEvaluation("CPA", SignalStatus.TRIGGERED, f"CPA increased {inc:.1f}%", value=current.cpa_cents, baseline_value=baseline.cpa_cents)
    return SignalEvaluation("CPA", SignalStatus.NORMAL, f"CPA is ${current.cpa_cents/100:.2f}", value=current.cpa_cents, baseline_value=baseline.cpa_cents)


def evaluate_conversion_rate(current: DerivedMetrics, baseline: Optional[DerivedMetrics]) -> SignalEvaluation:
    if current.conversion_rate is None:
        return SignalEvaluation("Conversion rate", SignalStatus.UNAVAILABLE, "No lead data")
    if baseline is None or baseline.conversion_rate is None:
        return SignalEvaluation("Conversion rate", SignalStatus.NORMAL, f"Conversion rate is {current.conversion_rate:.2f}%", value=current.conversion_rate)
    drop = ((baseline.conversion_rate - current.conversion_rate) / baseline.conversion_rate) * 100 if baseline.conversion_rate > 0 else 0
    if drop >= 30:
        return SignalEvaluation("Conversion rate", SignalStatus.TRIGGERED, f"Conversion rate dropped {drop:.1f}%", value=current.conversion_rate, baseline_value=baseline.conversion_rate)
    return SignalEvaluation("Conversion rate", SignalStatus.NORMAL, f"Conversion rate is {current.conversion_rate:.2f}%", value=current.conversion_rate, baseline_value=baseline.conversion_rate)


def evaluate_roas(current: DerivedMetrics) -> SignalEvaluation:
    if current.roas is None:
        return SignalEvaluation("ROAS", SignalStatus.UNAVAILABLE, "No revenue data")
    if current.roas < 1.0:
        return SignalEvaluation("ROAS", SignalStatus.TRIGGERED, f"ROAS is {current.roas:.2f}x - spending more than returning", value=current.roas)
    if current.roas < 2.0:
        return SignalEvaluation("ROAS", SignalStatus.CONCERNING, f"ROAS is {current.roas:.2f}x - thin margin", value=current.roas)
    return SignalEvaluation("ROAS", SignalStatus.NORMAL, f"ROAS is {current.roas:.2f}x", value=current.roas)


def evaluate_spend(current: RawTotals, daily_budget_cents: Optional[int]) -> SignalEvaluation:
    if not daily_budget_cents:
        return SignalEvaluation("Spend", SignalStatus.UNAVAILABLE, "No daily budget configured")
    utilization = (current.spend_cents / daily_budget_cents) * 100
    if utilization >= 95:
        return SignalEvaluation("Spend", SignalStatus.CONCERNING, f"Spend at {utilization:.0f}% of budget", value=current.spend_cents, baseline_value=daily_budget_cents)
    return SignalEvaluation("Spend", SignalStatus.NORMAL, f"Spend at {utilization:.0f}% of budget", value=current.spend_cents, baseline_value=daily_budget_cents)


def evaluate_frequency() -> SignalEvaluation:
    return SignalEvaluation("Frequency", SignalStatus.UNAVAILABLE, "This app does not sync Meta's frequency metric")


def evaluate_revenue(current: RawTotals, baseline: Optional[RawTotals]) -> SignalEvaluation:
    if current.revenue_cents is None:
        return SignalEvaluation("Revenue", SignalStatus.UNAVAILABLE, "No revenue data")
    if baseline is None or not baseline.revenue_cents:
        return SignalEvaluation("Revenue", SignalStatus.NORMAL, f"Revenue is ${current.revenue_cents/100:.2f}", value=current.revenue_cents)
    drop = ((baseline.revenue_cents - current.revenue_cents) / baseline.revenue_cents) * 100
    if drop >= 40:
        return SignalEvaluation("Revenue", SignalStatus.TRIGGERED, f"Revenue dropped {drop:.1f}%", value=current.revenue_cents, baseline_value=baseline.revenue_cents)
    return SignalEvaluation("Revenue", SignalStatus.NORMAL, f"Revenue is ${current.revenue_cents/100:.2f}", value=current.revenue_cents, baseline_value=baseline.revenue_cents)


def evaluate_lead_quality(average_lead_score: Optional[float] = None, baseline_average_lead_score: Optional[float] = None, lead_count: int = 0) -> SignalEvaluation:
    """
    As of Week 10, real when lead data is available -
    average_lead_score is the mean of real Lead.score (see
    app.leads.scoring) for this campaign's leads in the current period,
    computed by the caller (app.optimization.orchestrator, via
    app.leads.sales_agent_data.average_lead_score_for_campaign) and
    passed in here, since this module deliberately has no DB access of
    its own.
    """
    if average_lead_score is None or lead_count == 0:
        return SignalEvaluation("Lead quality", SignalStatus.UNAVAILABLE, "No leads are attributed to this campaign in this period yet")
    if baseline_average_lead_score is not None and baseline_average_lead_score > 0:
        drop_percent = ((baseline_average_lead_score - average_lead_score) / baseline_average_lead_score) * 100
        if drop_percent >= 30:
            return SignalEvaluation("Lead quality", SignalStatus.TRIGGERED, f"Average lead score dropped {drop_percent:.1f}% ({baseline_average_lead_score:.0f} -> {average_lead_score:.0f}) across {lead_count} lead(s)", value=average_lead_score, baseline_value=baseline_average_lead_score)
    if average_lead_score < 25:
        return SignalEvaluation("Lead quality", SignalStatus.TRIGGERED, f"Average lead score is {average_lead_score:.0f}/100 across {lead_count} lead(s)", value=average_lead_score)
    if average_lead_score < 45:
        return SignalEvaluation("Lead quality", SignalStatus.CONCERNING, f"Average lead score is {average_lead_score:.0f}/100 across {lead_count} lead(s)", value=average_lead_score)
    return SignalEvaluation("Lead quality", SignalStatus.NORMAL, f"Average lead score is {average_lead_score:.0f}/100 across {lead_count} lead(s)", value=average_lead_score)


def evaluate_campaign_objective(objective: str, current: DerivedMetrics) -> SignalEvaluation:
    if objective == "OUTCOME_LEADS" and current.conversion_rate is None:
        return SignalEvaluation("Campaign objective", SignalStatus.CONCERNING, "Objective is Leads but no lead data is measured")
    if objective == "OUTCOME_SALES" and current.roas is None:
        return SignalEvaluation("Campaign objective", SignalStatus.CONCERNING, "Objective is Sales but no revenue data is measured")
    return SignalEvaluation("Campaign objective", SignalStatus.NORMAL, f"Objective is {objective}, tracking looks consistent")


def evaluate_all(
    *,
    current_totals: RawTotals,
    current_derived: DerivedMetrics,
    baseline_totals: Optional[RawTotals],
    baseline_derived: Optional[DerivedMetrics],
    daily_budget_cents: Optional[int],
    campaign_objective: str,
    average_lead_score: Optional[float] = None,
    baseline_average_lead_score: Optional[float] = None,
    lead_count: int = 0,
) -> list:
    return [
        evaluate_ctr(current_derived, baseline_derived),
        evaluate_cpc(current_derived, baseline_derived),
        evaluate_cpm(current_derived, baseline_derived),
        evaluate_cpa(current_derived, baseline_derived),
        evaluate_conversion_rate(current_derived, baseline_derived),
        evaluate_roas(current_derived),
        evaluate_spend(current_totals, daily_budget_cents),
        evaluate_frequency(),
        evaluate_revenue(current_totals, baseline_totals),
        evaluate_lead_quality(average_lead_score, baseline_average_lead_score, lead_count),
        evaluate_campaign_objective(campaign_objective, current_derived),
    ]
