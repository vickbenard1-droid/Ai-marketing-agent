"""
Spend guard.

The single, narrow function permitted to authorize a spend-affecting
Meta Ads action (launching a campaign, changing a budget upward,
un-pausing anything with a budget). Every execution path in
app/meta_ads/execution_service.py calls assert_within_limits() FIRST,
before any Meta API call happens.

Design principles, all deliberate:

1. FAIL CLOSED ON MISSING CONFIGURATION. An ad account with no
   AdAccountSpendLimit row at all is blocked from every spend action -
   absence of a limit is never treated as "no limit configured, allow
   anything." A person must explicitly set a limit before this app will
   spend anything on their behalf.

2. EMERGENCY STOP CHECKED FIRST, IN ITS OWN BRANCH, BEFORE ANY NUMERIC
   COMPARISON. A bug in the daily-spend arithmetic below can never
   accidentally bypass an active stop, because the stop check doesn't
   depend on that arithmetic being correct at all.

3. REAL COMMITTED SPEND IS SUMMED FROM ACTUAL ROWS, NEVER TRUSTED FROM
   AN IN-MEMORY COUNTER. "How much is already committed today" is
   computed by querying real MetaCampaign daily_budget_cents values for
   ACTIVE campaigns under this ad account.

4. CAMPAIGN-LEVEL LIMITS ARE ADDITIVE, NEVER A LOOSER OVERRIDE. If a
   campaign has its own MetaCampaignSpendLimit, the proposed action must
   satisfy BOTH that limit AND the account-level limit.

5. THIS MODULE DOES NOT ITSELF CALL META. It is a narrow, mechanical
   gate over locally-known data.
"""
import uuid
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ad_account_spend_limit import AdAccountSpendLimit
from app.models.meta_campaign import MetaCampaign, MetaCampaignStatus
from app.models.meta_campaign_spend_limit import MetaCampaignSpendLimit


class SpendLimitExceededError(Exception):
    """Raised when a proposed spend action would exceed the applicable limit(s)."""


class EmergencyStopActiveError(Exception):
    """Raised when the ad account's emergency stop is active - blocks
    the action regardless of any numeric limit."""


class SpendLimitMissingError(Exception):
    """Raised when the ad account has no AdAccountSpendLimit row at all
    - fail closed, absence of a limit is never permission."""


def assert_within_limits(
    db: Session,
    *,
    meta_ad_account_id: uuid.UUID,
    proposed_daily_budget_cents: int,
    meta_campaign_id: Optional[uuid.UUID] = None,
) -> None:
    """
    Raises one of the exceptions above if this proposed daily budget
    would violate the account-level limit (and, if meta_campaign_id is
    given and has its own MetaCampaignSpendLimit row, the campaign-level
    limit too). Returns None if every check passes.
    """
    account_limit = (
        db.query(AdAccountSpendLimit).filter(AdAccountSpendLimit.meta_ad_account_id == meta_ad_account_id).first()
    )
    if not account_limit:
        raise SpendLimitMissingError(
            "No spend limit is configured for this ad account — set one before any spend action is permitted"
        )

    if account_limit.is_emergency_stopped:
        raise EmergencyStopActiveError(
            "This ad account's emergency stop is active"
            + (f": {account_limit.emergency_stop_reason}" if account_limit.emergency_stop_reason else "")
        )

    committed_cents = (
        db.query(func.coalesce(func.sum(MetaCampaign.daily_budget_cents), 0))
        .filter(
            MetaCampaign.meta_ad_account_id == meta_ad_account_id,
            MetaCampaign.status == MetaCampaignStatus.ACTIVE,
        )
        .scalar()
        or 0
    )
    if meta_campaign_id is not None:
        existing_campaign_budget = (
            db.query(func.coalesce(MetaCampaign.daily_budget_cents, 0))
            .filter(MetaCampaign.id == meta_campaign_id, MetaCampaign.status == MetaCampaignStatus.ACTIVE)
            .scalar()
            or 0
        )
        committed_cents -= existing_campaign_budget

    total_if_approved = committed_cents + proposed_daily_budget_cents
    if total_if_approved > account_limit.daily_spend_limit_cents:
        raise SpendLimitExceededError(
            f"Proposed daily budget would bring total committed daily spend to {total_if_approved} cents, "
            f"exceeding the account limit of {account_limit.daily_spend_limit_cents} cents"
        )

    if meta_campaign_id is not None:
        campaign_limit = (
            db.query(MetaCampaignSpendLimit)
            .filter(MetaCampaignSpendLimit.meta_campaign_id == meta_campaign_id)
            .first()
        )
        if campaign_limit is not None and proposed_daily_budget_cents > campaign_limit.daily_spend_limit_cents:
            raise SpendLimitExceededError(
                f"Proposed daily budget of {proposed_daily_budget_cents} cents exceeds this campaign's own "
                f"limit of {campaign_limit.daily_spend_limit_cents} cents"
            )
