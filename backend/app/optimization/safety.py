"""
Optimization safety module.

The concrete enforcement mechanism behind "Do not allow uncontrolled
spending" and the spec's SAFETY LIMITS section, mirroring
app.meta_ads.spend_guard's exact discipline (fail closed, emergency
stop checked first and separately, real committed state queried rather
than trusted from memory), extended to cover this week's additional
limits: campaign whitelist, max budget-increase percentage, and max
automated actions per day.

assert_can_execute_autonomously() is called FIRST, before any
autonomous execution - if it raises, no Meta API call happens.
Checked in this order: whitelist -> emergency stop -> settings exist ->
autonomy level permits this action -> daily action count -> budget-
increase percent (only if this action changes budget upward) -> daily
spend ceiling.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.analytics.metrics import RawTotals
from app.analytics.service import rollup_totals
from app.models.automated_action_log import AutomatedActionLog
from app.models.campaign_autonomy_settings import AutonomyLevel, CampaignAutonomySettings, CampaignWhitelist
from app.models.connected_account import PlatformType
from app.models.meta_campaign import MetaCampaign
from app.models.metric_snapshot import MetricEntityType
from app.models.optimization_decision import OptimizationActionType


class NotWhitelistedError(Exception):
    pass


class AutonomyEmergencyStopActiveError(Exception):
    pass


class AutonomySettingsMissingError(Exception):
    pass


class AutonomyLevelInsufficientError(Exception):
    pass


class DailyActionLimitExceededError(Exception):
    pass


class BudgetIncreaseLimitExceededError(Exception):
    pass


class DailySpendLimitExceededError(Exception):
    pass


def _assert_whitelisted(db: Session, organization_id: uuid.UUID, meta_campaign_id: uuid.UUID) -> None:
    entry = (
        db.query(CampaignWhitelist)
        .filter(CampaignWhitelist.organization_id == organization_id, CampaignWhitelist.meta_campaign_id == meta_campaign_id)
        .first()
    )
    if not entry:
        raise NotWhitelistedError("This campaign is not on the optimization agent's whitelist")


def _get_settings_or_raise(db: Session, meta_campaign_id: uuid.UUID) -> CampaignAutonomySettings:
    settings = db.query(CampaignAutonomySettings).filter(CampaignAutonomySettings.meta_campaign_id == meta_campaign_id).first()
    if not settings:
        raise AutonomySettingsMissingError("No autonomy settings configured for this campaign")
    return settings


def _assert_autonomy_permits(settings: CampaignAutonomySettings, action_type: OptimizationActionType) -> None:
    if settings.autonomy_level != AutonomyLevel.AUTONOMOUS:
        raise AutonomyLevelInsufficientError(f"Autonomy level is {settings.autonomy_level.value}, not eligible for autonomous execution")
    if action_type.value not in settings.auto_executable_action_types:
        raise AutonomyLevelInsufficientError(f"Action type '{action_type.value}' is not in this campaign's auto-executable list")


def _assert_daily_action_limit(db: Session, settings: CampaignAutonomySettings, meta_campaign_id: uuid.UUID) -> None:
    if settings.max_automated_actions_per_day is None:
        raise DailyActionLimitExceededError("No max_automated_actions_per_day limit is configured")
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    count_today = (
        db.query(AutomatedActionLog)
        .filter(AutomatedActionLog.meta_campaign_id == meta_campaign_id, AutomatedActionLog.executed_at >= today_start)
        .count()
    )
    if count_today >= settings.max_automated_actions_per_day:
        raise DailyActionLimitExceededError(f"Already had {count_today} action(s) today, at the limit of {settings.max_automated_actions_per_day}")


def _assert_budget_increase_within_limit(settings: CampaignAutonomySettings, current_daily_budget_cents: int, proposed_daily_budget_cents: int) -> None:
    if proposed_daily_budget_cents <= current_daily_budget_cents:
        return
    if settings.max_budget_increase_percent is None:
        raise BudgetIncreaseLimitExceededError("No max_budget_increase_percent limit is configured")
    if current_daily_budget_cents <= 0:
        raise BudgetIncreaseLimitExceededError("Cannot compute a percentage increase from a zero/unset current budget")
    increase_percent = ((proposed_daily_budget_cents - current_daily_budget_cents) / current_daily_budget_cents) * 100
    if increase_percent > settings.max_budget_increase_percent:
        raise BudgetIncreaseLimitExceededError(f"Proposed increase of {increase_percent:.1f}% exceeds the limit of {settings.max_budget_increase_percent}%")


def _assert_daily_spend_within_limit(db: Session, organization_id: uuid.UUID, settings: CampaignAutonomySettings, meta_campaign_id: uuid.UUID) -> None:
    if settings.max_daily_spend_cents is None:
        raise DailySpendLimitExceededError("No max_daily_spend_cents limit is configured")
    today = datetime.now(timezone.utc).date()
    totals: RawTotals = rollup_totals(
        db, organization_id, source=PlatformType.META_ADS, entity_type=MetricEntityType.CAMPAIGN, entity_id=meta_campaign_id, date_start=today, date_stop=today
    )
    if totals.spend_cents >= settings.max_daily_spend_cents:
        raise DailySpendLimitExceededError(f"Already spent {totals.spend_cents} cents today, at/above the limit of {settings.max_daily_spend_cents} cents")


def assert_can_execute_autonomously(
    db: Session,
    *,
    organization_id: uuid.UUID,
    meta_campaign_id: uuid.UUID,
    action_type: OptimizationActionType,
    proposed_daily_budget_cents: Optional[int] = None,
) -> None:
    _assert_whitelisted(db, organization_id, meta_campaign_id)
    settings = _get_settings_or_raise(db, meta_campaign_id)

    if settings.is_emergency_stopped:
        raise AutonomyEmergencyStopActiveError(
            "The optimization agent is emergency-stopped for this campaign" + (f": {settings.emergency_stop_reason}" if settings.emergency_stop_reason else "")
        )

    _assert_autonomy_permits(settings, action_type)
    _assert_daily_action_limit(db, settings, meta_campaign_id)

    if proposed_daily_budget_cents is not None:
        campaign = db.get(MetaCampaign, meta_campaign_id)
        current_budget = campaign.daily_budget_cents or 0
        _assert_budget_increase_within_limit(settings, current_budget, proposed_daily_budget_cents)

    _assert_daily_spend_within_limit(db, organization_id, settings, meta_campaign_id)
