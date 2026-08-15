"""
Celery tasks for outbound email. Endpoints call these via .delay()/.apply_async()
rather than calling app.mail.service.send_email() directly, so a slow or
failing SMTP connection never blocks the HTTP response for
register/forgot-password/etc.
"""
from app.mail.service import EmailContent, send_email
from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.send_email", bind=True, max_retries=3, default_retry_delay=30)
def send_email_task(self, *, to: str, subject: str, text_body: str, html_body: str | None = None):
    try:
        send_email(EmailContent(to=to, subject=subject, text_body=text_body, html_body=html_body))
    except Exception as exc:  # noqa: BLE001 — Celery retry needs the broad catch
        raise self.retry(exc=exc)
