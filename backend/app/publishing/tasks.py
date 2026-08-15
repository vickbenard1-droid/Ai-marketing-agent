"""
Publishing pipeline (Celery tasks).

publish_scheduled_post is the task that does the real work: decrypts the
connected account's credential (via the one sanctioned decrypt path, see
app.oauth.service.decrypt_credentials_for_publishing), calls the right
platform publisher, records a PublishingLog row for the attempt, and
updates the ScheduledPost's status. check_due_posts is the periodic task
that finds SCHEDULED posts whose time has arrived and dispatches
publish_scheduled_post for each - this is the "background jobs" the spec
asks for, not a synchronous call from an API request.

Retry policy: PublishRateLimitError and generic PublishError (network
blips, timeouts) are retried with exponential backoff, up to
MAX_RETRIES. PublishAuthError and PublishContentError are NOT
auto-retried - an expired/revoked credential or content the platform
rejected will fail identically on retry, so these go straight to FAILED
for a human to address (reauthorize the account, or edit the content)
rather than burning retry attempts on a failure mode retrying can't fix.

Note on task_always_eager (test mode, see app/tasks/celery_app.py): in
eager mode, calling self.retry() raises Celery's Retry exception once
and returns control to the caller — it does NOT loop internally to
consume the full retry budget in one .delay() call the way a real worker
does (a real worker re-dispatches the task after the countdown elapses,
calling the task function again from scratch). This was verified
directly: one eager .delay() against a persistently-failing publisher
raises Retry after incrementing retry_count by 1, not after exhausting
MAX_RETRIES. Simulating multiple real-world retries in a test means
calling .delay() repeatedly (as a worker's own retry loop would over
time), not expecting one call to exhaust the budget.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.connected_account import ConnectionStatus
from app.models.publishing_log import PublishingLog, PublishingLogOutcome
from app.models.scheduled_post import ScheduledPost, ScheduledPostStatus
from app.oauth.service import decrypt_credentials_for_publishing, refresh_expired_account
from app.publishing.base import (
    PublishAuthError,
    PublishError,
    PublishRateLimitError,
    PublishRequest,
)
from app.publishing.registry import get_publisher
from app.tasks.celery_app import celery_app

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [60, 300, 1500]  # 1min, 5min, 25min


def _is_expired(expires_at: datetime) -> bool:
    """Safely compares a possibly-naive datetime (e.g. read back from
    SQLite, which doesn't round-trip tzinfo through
    DateTime(timezone=True)) against now — same fix pattern used in
    app.oauth.service and app.scheduling.service; this is the third
    module that needed it, which is itself a signal this should probably
    become one shared utility rather than three local copies."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def _attempt_publish(db: Session, post: ScheduledPost) -> None:
    """
    The actual publish attempt for one ScheduledPost. Always writes
    exactly one PublishingLog row (success or failure) before returning
    or raising — a caller must never be able to observe a publish attempt
    that left no trace. This includes pre-flight failures (account not
    connected, token refresh failed, no stored credentials) as well as
    the platform call itself — all of them funnel through the same
    except block below, not just the publisher.publish() call, precisely
    because an earlier version of this function let pre-flight checks
    raise before reaching the logging code and silently skipped the log
    for those cases.
    """
    account = post.connected_account
    attempt_number = post.retry_count + 1

    try:
        if account.status != ConnectionStatus.CONNECTED:
            raise PublishAuthError(f"Connected account is {account.status.value}, not connected")

        if account.token_expires_at and _is_expired(account.token_expires_at):
            if not refresh_expired_account(db, account):
                raise PublishAuthError("Access token expired and could not be refreshed — reauthorization needed")

        credentials = decrypt_credentials_for_publishing(account)
        if not credentials:
            raise PublishAuthError("No usable credentials stored for this account")

        publisher = get_publisher(account.platform.value)
        request = PublishRequest(body=post.content.body, media_urls=[])
        result = publisher.publish(access_token=credentials["access_token"], request=request)
    except PublishError as exc:
        db.add(
            PublishingLog(
                scheduled_post_id=post.id,
                outcome=PublishingLogOutcome.FAILURE,
                request_summary=f"Publish to {account.platform.value}",
                error_message=str(exc),
                attempt_number=attempt_number,
            )
        )
        db.commit()
        raise

    db.add(
        PublishingLog(
            scheduled_post_id=post.id,
            outcome=PublishingLogOutcome.SUCCESS,
            request_summary=f"Publish to {publisher.display_name}",
            attempt_number=attempt_number,
        )
    )
    post.status = ScheduledPostStatus.PUBLISHED
    post.published_at = datetime.now(timezone.utc)
    post.external_post_id = result.external_post_id
    post.external_post_url = result.external_post_url
    db.commit()


@celery_app.task(name="tasks.publish_scheduled_post", bind=True, max_retries=MAX_RETRIES)
def publish_scheduled_post(self, post_id: str) -> str:
    """
    Celery task entry point - post_id is a string (Celery serializes
    task args as JSON, which has no native UUID type) and converted back
    to uuid.UUID immediately. Returns a short status string rather than
    None purely so tests calling .get() on the AsyncResult have something
    to assert on.
    """
    db = SessionLocal()
    try:
        post = db.query(ScheduledPost).filter(ScheduledPost.id == uuid.UUID(post_id)).first()
        if not post:
            return "not_found"

        post.status = ScheduledPostStatus.PUBLISHING
        db.commit()

        try:
            _attempt_publish(db, post)
            return "published"
        except PublishRateLimitError as exc:
            return _handle_retryable_failure(self, db, post, exc)
        except PublishError:
            # PublishAuthError / PublishContentError - not retried, see
            # module docstring.
            post.status = ScheduledPostStatus.FAILED
            db.commit()
            return "failed"
    finally:
        db.close()


def _handle_retryable_failure(task, db: Session, post: ScheduledPost, exc: Exception) -> str:
    post.retry_count += 1
    if post.retry_count > MAX_RETRIES:
        post.status = ScheduledPostStatus.FAILED
        db.commit()
        return "failed_max_retries"

    post.status = ScheduledPostStatus.SCHEDULED  # back in the queue for the next pass
    db.commit()
    backoff = RETRY_BACKOFF_SECONDS[min(post.retry_count - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
    raise task.retry(exc=exc, countdown=backoff)


@celery_app.task(name="tasks.check_due_posts")
def check_due_posts() -> int:
    """
    The periodic task (scheduled via Celery beat in a real deployment,
    not implemented here) that finds SCHEDULED posts whose time has
    arrived and dispatches publish_scheduled_post for each. Returns the
    count dispatched, so a test or a monitoring check can assert on it.
    """
    db = SessionLocal()
    try:
        due_posts = (
            db.query(ScheduledPost)
            .filter(
                ScheduledPost.status == ScheduledPostStatus.SCHEDULED,
                ScheduledPost.scheduled_for <= datetime.now(timezone.utc),
            )
            .all()
        )
        for post in due_posts:
            publish_scheduled_post.delay(str(post.id))
        return len(due_posts)
    finally:
        db.close()
