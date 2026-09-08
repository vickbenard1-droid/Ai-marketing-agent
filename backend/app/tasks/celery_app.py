"""
Celery application instance.

Real tasks defined elsewhere and registered against this app instance:
app.mail.tasks (email sending, Week 1) and app.publishing.tasks
(scheduled-post publishing + the due-post check, Week 6) — see those
modules for retry/timeout configuration.

HONEST GAP, found during the Week 12 performance review: no recurring/
scheduled Celery task exists for anything from Weeks 8-11 - Meta Ads
analytics sync (app.analytics.sync_orchestrator), the optimization
agent's campaign scan (app.optimization.orchestrator.scan_organization),
or any orchestrator work. All of that currently only runs synchronously,
on-demand, triggered by a real API request from a person (or would need
an external cron hitting those endpoints) - there is no periodic
background execution built into this app for that work. A production
deployment relying on the optimization agent actually running on a
schedule (rather than only when someone opens the dashboard and clicks
"scan now") would need this added; not built this week, since it's real
new infrastructure work, not a hardening fix, and is flagged explicitly
in the final production-readiness report rather than silently assumed
to exist.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai_marketing_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # In tests (APP_ENV=test, see app/tests/conftest.py) tasks run
    # synchronously in-process rather than requiring a live Redis broker —
    # this exercises the real task body (including email templating) inside
    # the test process without standing up a worker.
    task_always_eager=(settings.APP_ENV == "test"),
    task_eager_propagates=(settings.APP_ENV == "test"),
)


@celery_app.task(name="tasks.health_check")
def health_check() -> str:
    return "ok"
