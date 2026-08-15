"""
Scheduling service.

The content calendar's CRUD half - see app/publishing/tasks.py for the
Celery pipeline that actually publishes SCHEDULED posts when their time
arrives, and app/scheduling/recommendation_service.py for the AI
recommendation generation this module's accept_ai_recommendation()
consumes.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.models.connected_account import ConnectedAccount, ConnectionStatus
from app.models.content import Content
from app.models.scheduled_post import ScheduledPost, ScheduledPostStatus


class SchedulingError(Exception):
    """Raised for scheduling failures the API layer should turn into 4xx responses."""


def list_scheduled_posts(
    db: Session,
    organization_id: uuid.UUID,
    *,
    status: ScheduledPostStatus | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[ScheduledPost]:
    """
    Backs the calendar view. start/end filter on scheduled_for (for
    scheduled/published posts) - a draft with no scheduled_for yet is
    only returned when no date range is given, since it has no calendar
    slot to fall within.
    """
    query = db.query(ScheduledPost).filter(ScheduledPost.organization_id == organization_id)
    if status:
        query = query.filter(ScheduledPost.status == status)
    if start:
        query = query.filter(ScheduledPost.scheduled_for >= start)
    if end:
        query = query.filter(ScheduledPost.scheduled_for <= end)
    return query.order_by(ScheduledPost.scheduled_for.asc().nullslast()).all()


def get_scheduled_post(
    db: Session, *, organization_id: uuid.UUID, post_id: uuid.UUID
) -> ScheduledPost:
    post = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.id == post_id, ScheduledPost.organization_id == organization_id)
        .first()
    )
    if not post:
        raise SchedulingError("Scheduled post not found")
    return post


def _validate_content_and_account(
    db: Session, *, organization_id: uuid.UUID, content_id: uuid.UUID, connected_account_id: uuid.UUID
) -> None:
    content = (
        db.query(Content)
        .filter(Content.id == content_id, Content.organization_id == organization_id)
        .first()
    )
    if not content:
        raise SchedulingError("Content not found")

    account = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.id == connected_account_id, ConnectedAccount.organization_id == organization_id)
        .first()
    )
    if not account:
        raise SchedulingError("Connected account not found")
    if account.status != ConnectionStatus.CONNECTED:
        raise SchedulingError(
            f"This account is {account.status.value}, not connected — reauthorize it before scheduling"
        )


def create_draft_post(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    content_id: uuid.UUID,
    connected_account_id: uuid.UUID,
) -> ScheduledPost:
    _validate_content_and_account(
        db, organization_id=organization_id, content_id=content_id, connected_account_id=connected_account_id
    )
    post = ScheduledPost(
        organization_id=organization_id,
        created_by_user_id=actor_user_id,
        content_id=content_id,
        connected_account_id=connected_account_id,
        status=ScheduledPostStatus.DRAFT,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def _is_in_the_past(dt: datetime) -> bool:
    """Safely compares a possibly-naive datetime (e.g. read back from
    SQLite, which doesn't round-trip tzinfo through
    DateTime(timezone=True)) against now — same fix pattern as
    app.oauth.service._is_expired, applied here because schedule_post can
    receive a naive datetime two ways: directly from an API request body
    (Pydantic-parsed, should be aware) or from
    accept_ai_recommendation() passing back a value already read from the
    DB (ai_recommended_post_time), which is where this was actually
    caught — a naive value is treated as UTC rather than raising."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < datetime.now(timezone.utc)


def schedule_post(
    db: Session, *, organization_id: uuid.UUID, post_id: uuid.UUID, scheduled_for: datetime
) -> ScheduledPost:
    """Moves a DRAFT (or a FAILED post being rescheduled) to SCHEDULED
    with a concrete time - this is the human decision that actually
    queues the post for the publishing pipeline."""
    post = get_scheduled_post(db, organization_id=organization_id, post_id=post_id)
    if post.status == ScheduledPostStatus.PUBLISHED:
        raise SchedulingError("This post has already been published")
    if _is_in_the_past(scheduled_for):
        raise SchedulingError("Cannot schedule a post in the past")

    post.status = ScheduledPostStatus.SCHEDULED
    post.scheduled_for = scheduled_for
    db.commit()
    db.refresh(post)
    return post


def accept_ai_recommendation(
    db: Session, *, organization_id: uuid.UUID, post_id: uuid.UUID
) -> ScheduledPost:
    """
    The explicit, human-initiated action that copies
    ai_recommended_post_time into the real scheduled_for field - this is
    the ONLY code path that does so. See app/models/scheduled_post.py's
    module docstring: the AI's prediction sits inert in its own column
    until a person calls this (typically by clicking "use this time" in
    the UI), which is what keeps a recommendation from ever silently
    becoming a scheduling decision on its own.
    """
    post = get_scheduled_post(db, organization_id=organization_id, post_id=post_id)
    if not post.ai_recommended_post_time:
        raise SchedulingError("This post has no AI time recommendation to accept")
    return schedule_post(
        db, organization_id=organization_id, post_id=post_id, scheduled_for=post.ai_recommended_post_time
    )


def cancel_scheduled_post(
    db: Session, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID | None, post_id: uuid.UUID
) -> ScheduledPost:
    """Moves a SCHEDULED post back to DRAFT - pulls it out of the
    publishing pipeline's queue without deleting it."""
    post = get_scheduled_post(db, organization_id=organization_id, post_id=post_id)
    if post.status == ScheduledPostStatus.PUBLISHED:
        raise SchedulingError("Cannot cancel a post that has already been published")

    post.status = ScheduledPostStatus.DRAFT
    post.scheduled_for = None

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="scheduled_post.cancelled",
        resource_type="ScheduledPost",
        resource_id=str(post.id),
    )

    db.commit()
    db.refresh(post)
    return post


def delete_scheduled_post(db: Session, *, organization_id: uuid.UUID, post_id: uuid.UUID) -> None:
    post = get_scheduled_post(db, organization_id=organization_id, post_id=post_id)
    if post.status == ScheduledPostStatus.PUBLISHED:
        raise SchedulingError("Cannot delete a post that has already been published — its record is kept")
    db.delete(post)
    db.commit()
