"""
Outbound email via SMTP (smtplib, stdlib — no extra dependency needed for
a synchronous send, which is fine since this is always called from a
Celery task, never inline on a request).

Real SMTP is configured via SMTP_HOST/PORT/USERNAME/PASSWORD in .env (see
.env.example). If SMTP_HOST is unset, send_email() logs the email instead
of raising — this keeps local dev usable without real SMTP credentials
while still exercising every code path around it. Set SMTP_HOST to a local
catcher (e.g. Mailhog on localhost:1025) or a real provider (SES, Mailgun,
Gmail with an app password, etc.) for actual delivery.
"""
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("app.mail")


class MailError(Exception):
    """Raised when an email fails to send via a configured SMTP server."""


@dataclass
class EmailContent:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None


def send_email(content: EmailContent) -> None:
    if not settings.SMTP_HOST:
        # No SMTP configured — log instead of failing. This is what lets
        # `docker compose up` work out of the box without SMTP creds; set
        # SMTP_HOST to get real delivery. Logged at INFO, not DEBUG, since
        # in this mode it's the only record that the email "was sent."
        logger.info(
            "SMTP_HOST not configured — logging email instead of sending.\n"
            "To: %s\nSubject: %s\n\n%s",
            content.to,
            content.subject,
            content.text_body,
        )
        return

    message = EmailMessage()
    message["Subject"] = content.subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = content.to
    message.set_content(content.text_body)
    if content.html_body:
        message.add_alternative(content.html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Never let an email failure surface a stack trace to the caller —
        # the caller (a Celery task) should retry/log, not crash the
        # request that triggered it (registration, password reset request).
        logger.error("Failed to send email to %s: %s", content.to, exc)
        raise MailError(str(exc)) from exc
