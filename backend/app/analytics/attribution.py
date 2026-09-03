"""
Attribution module.

Computes first-touch, last-touch, and campaign-level attribution ON
DEMAND from ConversionEvent.touchpoints_json's raw ordered history -
never a pre-picked "the" attributed touchpoint stored anywhere. This is
the concrete implementation of the design principle documented on
ConversionEvent itself: storing one pre-computed answer would silently
privilege one attribution model over every other equally-valid one.

Every result explicitly carries a `limitations` list - attribution is
inherently a modeling choice, not a fact, and every function here is
honest about what it cannot claim:
1. A touchpoint history only contains what this app actually observed -
   a channel this app has no tracking for (e.g. an offline referral)
   is invisible to this data, not "confirmed absent."
2. First/last touch are two of many possible models (linear, time-decay,
   etc. are not implemented) - picking one is a real methodological
   choice this app makes explicit, not hidden.
3. A conversion with NO touchpoints at all (e.g. a walk-in) has no
   attribution to compute - returns None with a limitation explaining
   why, never guesses.
4. A conversion with exactly ONE touchpoint has technically-unambiguous
   first/last touch (they're the same touchpoint) but this is flagged
   as low-signal, not a strong finding.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Touchpoint:
    source: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    touched_at: datetime


@dataclass
class AttributionResult:
    attributed_touchpoint: Optional[Touchpoint]
    limitations: list = field(default_factory=list)


def _parse_touchpoints(raw: list) -> list:
    parsed = []
    for entry in raw:
        try:
            touched_at = datetime.fromisoformat(entry["touched_at"].replace("Z", "+00:00"))
            parsed.append(
                Touchpoint(
                    source=entry.get("source", "unknown"),
                    entity_type=entry.get("entity_type"),
                    entity_id=entry.get("entity_id"),
                    touched_at=touched_at,
                )
            )
        except (KeyError, ValueError, AttributeError):
            continue  # a malformed touchpoint entry is skipped, not fatal to the whole conversion
    return parsed


def first_touch(raw_touchpoints: list) -> AttributionResult:
    touchpoints = _parse_touchpoints(raw_touchpoints)
    if not touchpoints:
        return AttributionResult(
            attributed_touchpoint=None,
            limitations=["No touchpoint data exists for this conversion — this reflects what was tracked, not necessarily that none occurred"],
        )
    earliest = min(touchpoints, key=lambda t: t.touched_at)
    limitations = []
    if len(touchpoints) == 1:
        limitations.append("Only one touchpoint recorded — first-touch and last-touch are the same here, low signal")
    return AttributionResult(attributed_touchpoint=earliest, limitations=limitations)


def last_touch(raw_touchpoints: list) -> AttributionResult:
    touchpoints = _parse_touchpoints(raw_touchpoints)
    if not touchpoints:
        return AttributionResult(
            attributed_touchpoint=None,
            limitations=["No touchpoint data exists for this conversion — this reflects what was tracked, not necessarily that none occurred"],
        )
    latest = max(touchpoints, key=lambda t: t.touched_at)
    limitations = []
    if len(touchpoints) == 1:
        limitations.append("Only one touchpoint recorded — first-touch and last-touch are the same here, low signal")
    return AttributionResult(attributed_touchpoint=latest, limitations=limitations)


@dataclass
class CampaignAttributionSummary:
    meta_campaign_id: str
    attributed_conversion_count: int
    total_conversions_considered: int
    conversions_with_no_touchpoint_data: int
    limitations: list = field(default_factory=list)


def campaign_level(meta_campaign_id: str, all_touchpoint_lists: list, *, model: str = "last_touch") -> CampaignAttributionSummary:
    """Aggregates attribution across MANY conversions' touchpoint
    histories, counting how many are attributed to one specific
    campaign under the given model."""
    if model not in ("first_touch", "last_touch"):
        raise ValueError(f"Unsupported attribution model: {model}")
    attribution_fn = first_touch if model == "first_touch" else last_touch

    attributed_count = 0
    no_data_count = 0
    for touchpoints in all_touchpoint_lists:
        result = attribution_fn(touchpoints)
        if result.attributed_touchpoint is None:
            no_data_count += 1
            continue
        if result.attributed_touchpoint.entity_id == meta_campaign_id:
            attributed_count += 1

    limitations = [f"Computed under the '{model}' attribution model — a different model may attribute differently"]
    if no_data_count > 0:
        limitations.append(f"{no_data_count} conversion(s) had no touchpoint data and could not be attributed to anything")

    return CampaignAttributionSummary(
        meta_campaign_id=meta_campaign_id,
        attributed_conversion_count=attributed_count,
        total_conversions_considered=len(all_touchpoint_lists),
        conversions_with_no_touchpoint_data=no_data_count,
        limitations=limitations,
    )
