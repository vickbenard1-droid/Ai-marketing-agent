"""
Celery application instance.

No real background tasks are defined yet — this is wiring for future weeks
(scheduled content publishing, campaign performance polling, optimization
job execution). A trivial health-check task is included so the worker setup
can be verified end-to-end this week.
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
