"""
Experiment service.

create_experiment validates that variant_ids actually reference real
AdCopyVariant/CreativeConcept rows belonging to the campaign (for
dimension in headline/hook/creative) — an experiment pointing at a
nonexistent or cross-campaign id would silently break the review UI
later, so this is checked at creation time rather than left to surface as
a confusing lookup failure downstream. For dimension=audience, entries
are freeform strings (no row to validate against — see
app/models/experiment.py's own docstring), so any non-blank strings pass.
"""
import uuid

from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.campaigns.service import get_campaign
from app.models.experiment import Experiment, ExperimentDimension


class ExperimentError(Exception):
    """Raised for experiment failures the API layer should turn into 4xx responses."""


def list_experiments(db: Session, *, organization_id: uuid.UUID, campaign_id: uuid.UUID) -> list[Experiment]:
    campaign = get_campaign(db, organization_id=organization_id, campaign_id=campaign_id)
    return campaign.experiments


def create_experiment(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    campaign_id: uuid.UUID,
    name: str,
    dimension: ExperimentDimension,
    description: str | None,
    variant_ids: list[str],
) -> Experiment:
    campaign = get_campaign(db, organization_id=organization_id, campaign_id=campaign_id)

    if dimension in (ExperimentDimension.HEADLINE, ExperimentDimension.HOOK):
        valid_ids = {str(v.id) for v in campaign.ad_copy_variants}
        # HOOK experiments test hook *creative concepts*, not ad copy —
        # but a hook can also be expressed as a headline variant
        # depending on how the business is testing it, so both id pools
        # are accepted for HOOK; HEADLINE only accepts ad copy variant ids.
        if dimension == ExperimentDimension.HOOK:
            valid_ids |= {str(c.id) for c in campaign.creative_concepts}
        unknown = [v for v in variant_ids if v not in valid_ids]
        if unknown:
            raise ExperimentError(
                f"These ids don't belong to this campaign's ad copy/creative: {unknown}"
            )
    elif dimension == ExperimentDimension.CREATIVE:
        valid_ids = {str(c.id) for c in campaign.creative_concepts}
        unknown = [v for v in variant_ids if v not in valid_ids]
        if unknown:
            raise ExperimentError(f"These ids don't belong to this campaign's creative concepts: {unknown}")
    # ExperimentDimension.AUDIENCE: freeform strings, nothing to validate against.

    experiment = Experiment(
        campaign_id=campaign.id,
        name=name,
        dimension=dimension,
        description=description,
        variant_ids=variant_ids,
    )
    db.add(experiment)
    db.flush()

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="experiment.created",
        resource_type="Experiment",
        resource_id=str(experiment.id),
        metadata={"campaign_id": str(campaign_id), "dimension": dimension.value},
    )

    db.commit()
    db.refresh(experiment)
    return experiment
