"""
Tests for app.publishing.tasks - dispatches real Celery tasks via .delay()
(task_always_eager=True in test mode, see app/tasks/celery_app.py) rather
than calling the underlying function directly, so these exercise the
actual Celery task wrapper (retry/max_retries handling, task
serialization) rather than bypassing it.

Uses the db_session fixture's StaticPool-backed engine and monkeypatches
app.publishing.tasks.SessionLocal to point at it, since the task
otherwise opens its own SessionLocal() - a production DATABASE_URL-backed
connection, not the test's in-memory one.
"""
import json

import httpx
import pytest
from unittest.mock import MagicMock, patch

import app.publishing.tasks as tasks
from app.core.security import encrypt_secret
import app.models as m


@pytest.fixture()
def seeded_post(db_session):
    """A CONNECTED account with real encrypted credentials and one
    SCHEDULED post - the common starting state for every test below."""
    org = m.Organization(name="Acme", slug="acme")
    db_session.add(org)
    db_session.flush()
    project = m.Project(organization_id=org.id, name="Default")
    db_session.add(project)
    db_session.flush()

    creds_blob = encrypt_secret(json.dumps({"access_token": "real-token", "refresh_token": None}))
    account = m.ConnectedAccount(
        organization_id=org.id,
        project_id=project.id,
        platform=m.PlatformType.FACEBOOK_PAGE,
        status=m.ConnectionStatus.CONNECTED,
        encrypted_credentials=creds_blob,
    )
    db_session.add(account)
    db_session.flush()

    content = m.Content(organization_id=org.id, content_type=m.ContentType.FACEBOOK_POST, body="Check out our candles!")
    db_session.add(content)
    db_session.flush()

    post = m.ScheduledPost(
        organization_id=org.id,
        content_id=content.id,
        connected_account_id=account.id,
        status=m.ScheduledPostStatus.SCHEDULED,
    )
    db_session.add(post)
    db_session.commit()
    return post


@pytest.fixture(autouse=True)
def _patch_session_local(db_session, monkeypatch):
    """Every test in this file runs the real task, so it needs to use
    the test's own session/connection rather than opening a fresh one
    against production config."""
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(tasks, "SessionLocal", TestSessionLocal)


def _mock_response(json_body=None, status=200, text=""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.json.return_value = json_body or {}
    resp.text = text or str(json_body)
    return resp


def test_publish_success_end_to_end(db_session, seeded_post):
    with patch("httpx.Client.post", return_value=_mock_response({"id": "fb_post_999"})):
        result = tasks.publish_scheduled_post.delay(str(seeded_post.id))
        assert result.get() == "published"

    db_session.expire_all()
    post = db_session.get(m.ScheduledPost, seeded_post.id)
    assert post.status == m.ScheduledPostStatus.PUBLISHED
    assert post.external_post_id == "fb_post_999"
    assert post.published_at is not None
    assert len(post.publishing_logs) == 1
    assert post.publishing_logs[0].outcome == m.PublishingLogOutcome.SUCCESS


def test_preflight_failure_still_writes_a_log(db_session):
    """Regression test for a real bug found during development: a
    disconnected account (or missing credentials) used to raise before
    reaching the log-writing code, silently skipping the publishing log
    the spec explicitly requires."""
    org = m.Organization(name="Acme", slug="acme")
    db_session.add(org)
    db_session.flush()
    project = m.Project(organization_id=org.id, name="Default")
    db_session.add(project)
    db_session.flush()
    account = m.ConnectedAccount(
        organization_id=org.id,
        project_id=project.id,
        platform=m.PlatformType.FACEBOOK_PAGE,
        status=m.ConnectionStatus.CONNECTED,
        encrypted_credentials=None,
    )
    db_session.add(account)
    db_session.flush()
    content = m.Content(organization_id=org.id, content_type=m.ContentType.FACEBOOK_POST, body="x")
    db_session.add(content)
    db_session.flush()
    post = m.ScheduledPost(
        organization_id=org.id, content_id=content.id, connected_account_id=account.id,
        status=m.ScheduledPostStatus.SCHEDULED,
    )
    db_session.add(post)
    db_session.commit()

    result = tasks.publish_scheduled_post.delay(str(post.id))
    assert result.get() == "failed"

    db_session.expire_all()
    fetched = db_session.get(m.ScheduledPost, post.id)
    assert fetched.status == m.ScheduledPostStatus.FAILED
    assert len(fetched.publishing_logs) == 1
    assert fetched.publishing_logs[0].outcome == m.PublishingLogOutcome.FAILURE
    assert "credentials" in fetched.publishing_logs[0].error_message.lower()


def test_auth_error_is_not_retried(db_session, seeded_post):
    """A 401/403 (PublishAuthError) should go straight to FAILED - never
    retried, since an expired/revoked credential will fail identically
    on every retry."""
    with patch("httpx.Client.post", return_value=_mock_response(status=401, text="invalid token")):
        result = tasks.publish_scheduled_post.delay(str(seeded_post.id))
        assert result.get() == "failed"

    db_session.expire_all()
    post = db_session.get(m.ScheduledPost, seeded_post.id)
    assert post.status == m.ScheduledPostStatus.FAILED
    assert post.retry_count == 0


def test_rate_limit_retries_then_eventually_fails(db_session, seeded_post):
    """
    Verifies the retry/backoff path by simulating what a real worker
    does: calling the task repeatedly (as Celery's own retry mechanism
    would after each backoff period elapses in production), not
    expecting one eager .delay() call to exhaust the whole retry budget
    - task_always_eager raises Retry once per call rather than looping
    internally (see app/publishing/tasks.py's own note on this).
    """
    with patch("httpx.Client.post", return_value=_mock_response(status=429, text="rate limited")):
        for expected_retry_count in range(1, tasks.MAX_RETRIES + 1):
            with pytest.raises(Exception):
                tasks.publish_scheduled_post.delay(str(seeded_post.id)).get()
            db_session.expire_all()
            post = db_session.get(m.ScheduledPost, seeded_post.id)
            assert post.status == m.ScheduledPostStatus.SCHEDULED
            assert post.retry_count == expected_retry_count

        result = tasks.publish_scheduled_post.delay(str(seeded_post.id))
        assert result.get() == "failed_max_retries"

    db_session.expire_all()
    post = db_session.get(m.ScheduledPost, seeded_post.id)
    assert post.status == m.ScheduledPostStatus.FAILED
    assert len(post.publishing_logs) == tasks.MAX_RETRIES + 1
    assert all(log.outcome == m.PublishingLogOutcome.FAILURE for log in post.publishing_logs)


def test_check_due_posts_only_dispatches_due_and_scheduled_posts(db_session):
    from datetime import datetime, timedelta, timezone

    org = m.Organization(name="Acme", slug="acme")
    db_session.add(org)
    db_session.flush()
    project = m.Project(organization_id=org.id, name="Default")
    db_session.add(project)
    db_session.flush()
    account = m.ConnectedAccount(
        organization_id=org.id, project_id=project.id, platform=m.PlatformType.FACEBOOK_PAGE,
        status=m.ConnectionStatus.CONNECTED,
        encrypted_credentials=encrypt_secret(json.dumps({"access_token": "t", "refresh_token": None})),
    )
    db_session.add(account)
    db_session.flush()
    content = m.Content(organization_id=org.id, content_type=m.ContentType.FACEBOOK_POST, body="x")
    db_session.add(content)
    db_session.flush()

    now = datetime.now(timezone.utc)
    due_post = m.ScheduledPost(
        organization_id=org.id, content_id=content.id, connected_account_id=account.id,
        status=m.ScheduledPostStatus.SCHEDULED, scheduled_for=now - timedelta(minutes=5),
    )
    future_post = m.ScheduledPost(
        organization_id=org.id, content_id=content.id, connected_account_id=account.id,
        status=m.ScheduledPostStatus.SCHEDULED, scheduled_for=now + timedelta(hours=1),
    )
    draft_post = m.ScheduledPost(
        organization_id=org.id, content_id=content.id, connected_account_id=account.id,
        status=m.ScheduledPostStatus.DRAFT, scheduled_for=None,
    )
    db_session.add_all([due_post, future_post, draft_post])
    db_session.commit()

    with patch("httpx.Client.post", return_value=_mock_response({"id": "post123"})):
        dispatched_count = tasks.check_due_posts.delay().get()

    assert dispatched_count == 1

    db_session.expire_all()
    assert db_session.get(m.ScheduledPost, due_post.id).status == m.ScheduledPostStatus.PUBLISHED
    assert db_session.get(m.ScheduledPost, future_post.id).status == m.ScheduledPostStatus.SCHEDULED
    assert db_session.get(m.ScheduledPost, draft_post.id).status == m.ScheduledPostStatus.DRAFT
