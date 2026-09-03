"""
Metrics calculation module.

Pure functions only - no DB access. Callers (app/analytics/service.py)
sum real MetricSnapshot rows into a RawTotals, then pass it here to
compute derived ratios. Every derived function returns None (never a
fabricated 0 or a divide-by-zero exception) when its inputs are missing
or would produce a mathematically undefined result - this is the
concrete mechanism behind "do not fabricate statistics": a None is an
honest "this can't be computed from what's known," clearly distinct
from a real 0, which callers/AI-facing code must never blur together.

Two genuinely different kinds of "missing" are both handled, correctly
kept distinct:
- A count that is 0 (e.g. zero purchases this period - a real,
  measured fact) vs.
- A count that is None (this source never reports this metric at all,
  e.g. Shopify doesn't report impressions - genuinely unmeasured, not
  zero).
Every ratio function checks for BOTH: a None numerator/denominator input
propagates to a None result, and a zero denominator also produces None
(never a fabricated infinity or a silently-wrong 0).
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class RawTotals:
    """The raw, summed inputs every derived-metric function needs.
    Callers build this by summing MetricSnapshot rows over whatever
    date range/entity scope is relevant."""

    impressions: int = 0
    clicks: int = 0
    spend_cents: int = 0
    leads_count: Optional[int] = None
    purchases_count: Optional[int] = None
    revenue_cents: Optional[int] = None
    reach: Optional[int] = None


@dataclass
class DerivedMetrics:
    ctr: Optional[float]
    cpc_cents: Optional[float]
    cpm_cents: Optional[float]
    cost_per_lead_cents: Optional[float]
    cpa_cents: Optional[float]
    roas: Optional[float]
    conversion_rate: Optional[float]


def ctr(totals: RawTotals) -> Optional[float]:
    if totals.impressions == 0:
        return None
    return (totals.clicks / totals.impressions) * 100


def cpc_cents(totals: RawTotals) -> Optional[float]:
    if totals.clicks == 0:
        return None
    return totals.spend_cents / totals.clicks


def cpm_cents(totals: RawTotals) -> Optional[float]:
    if totals.impressions == 0:
        return None
    return (totals.spend_cents / totals.impressions) * 1000


def cost_per_lead_cents(totals: RawTotals) -> Optional[float]:
    if totals.leads_count is None or totals.leads_count == 0:
        return None
    return totals.spend_cents / totals.leads_count


def cpa_cents(totals: RawTotals) -> Optional[float]:
    if totals.purchases_count is None or totals.purchases_count == 0:
        return None
    return totals.spend_cents / totals.purchases_count


def roas(totals: RawTotals) -> Optional[float]:
    if totals.revenue_cents is None or totals.spend_cents == 0:
        return None
    return totals.revenue_cents / totals.spend_cents


def conversion_rate(totals: RawTotals) -> Optional[float]:
    if totals.clicks == 0 or totals.leads_count is None:
        return None
    return (totals.leads_count / totals.clicks) * 100


def compute_all(totals: RawTotals) -> DerivedMetrics:
    return DerivedMetrics(
        ctr=ctr(totals),
        cpc_cents=cpc_cents(totals),
        cpm_cents=cpm_cents(totals),
        cost_per_lead_cents=cost_per_lead_cents(totals),
        cpa_cents=cpa_cents(totals),
        roas=roas(totals),
        conversion_rate=conversion_rate(totals),
    )
