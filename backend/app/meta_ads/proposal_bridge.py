"""
Campaign generation bridge.

Translates a Week 4 internal Campaign (status=APPROVED, meaning a human
has reviewed the AI-generated strategy/audience/copy) into a concrete
MetaCampaignProposal.

Deliberately produces a PROPOSAL, not an immediate MetaCampaign row -
launching to Meta is still a real external side effect requiring its
own explicit human action, gated by the spend guard the same as every
other spend-affecting action.

HONEST GAP: Campaign.target_audience is a free-text description -
Meta's real targeting spec needs structured interest/behavior IDs from
Meta's own targeting search API, which this bridge does not call.
build_meta_campaign_proposal() returns None for targeting_spec and
flags this in unresolved_fields rather than fabricating a
plausible-looking but fake targeting spec - a person must manually
configure real targeting before this campaign can actually launch.
"""
from dataclasses import dataclass, field
from typing import Optional

from app.models.campaign import Campaign, MarketingObjective
from app.models.meta_campaign import MetaCampaignObjective

_OBJECTIVE_MAP = {
    MarketingObjective.SALES: MetaCampaignObjective.OUTCOME_SALES,
    MarketingObjective.LEADS: MetaCampaignObjective.OUTCOME_LEADS,
    MarketingObjective.WEBSITE_TRAFFIC: MetaCampaignObjective.OUTCOME_TRAFFIC,
    MarketingObjective.BRAND_AWARENESS: MetaCampaignObjective.OUTCOME_AWARENESS,
}


@dataclass
class MetaCampaignProposal:
    name: str
    objective: MetaCampaignObjective
    daily_budget_cents: Optional[int]
    targeting_spec: Optional[dict]
    unresolved_fields: list = field(default_factory=list)


class CampaignBridgeError(Exception):
    """Raised when a Campaign cannot be translated into a proposal at all."""


def build_meta_campaign_proposal(campaign: Campaign) -> MetaCampaignProposal:
    if campaign.status.value != "approved":
        raise CampaignBridgeError(
            f"Only an APPROVED campaign can be proposed for Meta launch (current status: {campaign.status.value})"
        )

    objective = _OBJECTIVE_MAP.get(campaign.objective)
    if objective is None:
        raise CampaignBridgeError(f"No Meta objective mapping exists for '{campaign.objective.value}'")

    unresolved = []

    daily_budget_cents = None
    if campaign.budget_amount is not None and campaign.duration_days:
        daily_budget_cents = round((campaign.budget_amount / campaign.duration_days) * 100)
    elif campaign.budget_amount is not None:
        unresolved.append(
            "No duration_days set — cannot derive a daily budget from the total budget_amount alone; "
            "a person must specify one before launch"
        )
    else:
        unresolved.append("No budget_amount set at all — a person must set a budget before launch")

    targeting_spec = None
    unresolved.append(
        "targeting_spec could not be resolved — Campaign.target_audience is a free-text description; "
        "Meta's real ad-set targeting requires structured interest/behavior IDs from Meta's targeting "
        "search API, which this bridge does not call. Configure real targeting manually before launch."
    )

    return MetaCampaignProposal(
        name=campaign.product_name,
        objective=objective,
        daily_budget_cents=daily_budget_cents,
        targeting_spec=targeting_spec,
        unresolved_fields=unresolved,
    )
