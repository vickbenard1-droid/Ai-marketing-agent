"""
Scheduled post (content calendar) endpoints.

Reading (list/get) requires only org membership - the calendar view.
Creating/scheduling/cancelling/deleting is gated on can_manage_content
(same permission that gates Content itself - scheduling a piece of
content to go out is a content-management action). Posting recommendation
generation is gated on can_execute_ai_actions, matching every other
AI-cost-incurring action in this app.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.models.scheduled_post import ScheduledPostStatus
from app.publishing.tasks import publish_scheduled_post
from app.scheduling.recommendation_service import RecommendationError, generate_posting_recommendation
from app.scheduling.service import (
    SchedulingError,
    accept_ai_recommendation,
    cancel_scheduled_post,
    create_draft_post,
    delete_scheduled_post,
    get_scheduled_post,
    list_scheduled_posts,
    schedule_post,
)
from app.schemas.auth import MessageResponse
from app.schemas.scheduled_post import (
    CreateDraftPostRequest,
    ScheduledPostDetail,
    ScheduledPostPublic,
    SchedulePostRequest,
)

router = APIRouter(prefix="/scheduled-posts", tags=["scheduled-posts"])


@router.get("", response_model=list[ScheduledPostPublic])
def list_my_scheduled_posts(
    status_filter: ScheduledPostStatus | None = Query(default=None, alias="status"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    """Backs the calendar view - day/week/month is a frontend concern
    (choosing the start/end range to request), this endpoint just filters
    by whatever range and status is asked for."""
    return list_scheduled_posts(db, member.organization_id, status=status_filter, start=start, end=end)


@router.post("", response_model=ScheduledPostPublic, status_code=status.HTTP_201_CREATED)
def create_draft(
    payload: CreateDraftPostRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        return create_draft_post(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            content_id=payload.content_id,
            connected_account_id=payload.connected_account_id,
        )
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{post_id}", response_model=ScheduledPostDetail)
def get_my_scheduled_post(
    post_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        return get_scheduled_post(db, organization_id=member.organization_id, post_id=post_id)
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{post_id}/schedule", response_model=ScheduledPostPublic)
def schedule_my_post(
    post_id: uuid.UUID,
    payload: SchedulePostRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        return schedule_post(
            db, organization_id=member.organization_id, post_id=post_id, scheduled_for=payload.scheduled_for
        )
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{post_id}/publish-now", response_model=ScheduledPostPublic)
def publish_now(
    post_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    """
    Dispatches the same Celery task the scheduled pipeline uses
    (app.publishing.tasks.publish_scheduled_post) immediately rather than
    waiting for a scheduled_for time - the spec's explicit "Publish now"
    requirement. Uses .delay() so this goes through the real background
    job mechanism (task_always_eager runs it synchronously in tests, see
    app/tasks/celery_app.py) rather than calling the publish logic
    directly from the request handler.
    """
    try:
        post = get_scheduled_post(db, organization_id=member.organization_id, post_id=post_id)
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    publish_scheduled_post.delay(str(post.id))
    db.refresh(post)
    return post


@router.post("/{post_id}/retry", response_model=ScheduledPostPublic)
def retry_failed_post(
    post_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    """Re-dispatches a FAILED post through the publishing pipeline - the
    spec's explicit "Retry failed posts" requirement. Only meaningful for
    FAILED posts; dispatching an already-PUBLISHED post again would
    double-post, so this is rejected rather than silently re-running."""
    try:
        post = get_scheduled_post(db, organization_id=member.organization_id, post_id=post_id)
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if post.status != ScheduledPostStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only a failed post can be retried (current status: {post.status.value})",
        )

    publish_scheduled_post.delay(str(post.id))
    db.refresh(post)
    return post


@router.post("/{post_id}/cancel", response_model=ScheduledPostPublic)
def cancel_my_post(
    post_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        return cancel_scheduled_post(
            db, organization_id=member.organization_id, actor_user_id=member.user_id, post_id=post_id
        )
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{post_id}", response_model=MessageResponse)
def delete_my_post(
    post_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        delete_scheduled_post(db, organization_id=member.organization_id, post_id=post_id)
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return MessageResponse(message="Scheduled post deleted")


@router.post("/{post_id}/recommend", response_model=ScheduledPostPublic)
def recommend_posting(
    post_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
    db: Session = Depends(get_db),
):
    try:
        return generate_posting_recommendation(
            db, organization_id=member.organization_id, actor_user_id=member.user_id, scheduled_post_id=post_id
        )
    except RecommendationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{post_id}/accept-recommendation", response_model=ScheduledPostPublic)
def accept_recommendation(
    post_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    """
    The explicit human action that copies the AI's time prediction into
    the real scheduled_for field. Gated on can_manage_content (a
    scheduling decision), not can_execute_ai_actions (this doesn't call
    the AI - the recommendation already exists on the post from a prior
    /recommend call).
    """
    try:
        return accept_ai_recommendation(db, organization_id=member.organization_id, post_id=post_id)
    except SchedulingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
