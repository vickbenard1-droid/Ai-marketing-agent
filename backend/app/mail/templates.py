"""
Plain-text + minimal HTML templates for transactional emails.

Kept as simple string templates rather than a templating engine (Jinja2,
MJML, etc.) — the email surface is two messages this week, and pulling in
a template engine for that is premature. Revisit if the number of
transactional emails grows past a handful.
"""
from app.mail.service import EmailContent


def verification_email(*, to: str, full_name: str, verify_url: str) -> EmailContent:
    first_name = full_name.split(" ")[0] if full_name else "there"
    text_body = (
        f"Hi {first_name},\n\n"
        f"Confirm your email address to finish setting up your AI Marketing "
        f"Agent account:\n\n{verify_url}\n\n"
        f"This link expires in 24 hours. If you didn't create this account, "
        f"you can ignore this email.\n"
    )
    html_body = f"""\
<div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
  <p>Hi {first_name},</p>
  <p>Confirm your email address to finish setting up your AI Marketing Agent account.</p>
  <p><a href="{verify_url}" style="display:inline-block;background:#12161F;color:#fff;
     padding:10px 20px;border-radius:6px;text-decoration:none;">Verify email</a></p>
  <p style="color:#7C89A3;font-size:13px;">This link expires in 24 hours. If you didn't
     create this account, you can ignore this email.</p>
</div>
"""
    return EmailContent(
        to=to,
        subject="Verify your email — AI Marketing Agent",
        text_body=text_body,
        html_body=html_body,
    )


def password_reset_email(*, to: str, full_name: str, reset_url: str) -> EmailContent:
    first_name = full_name.split(" ")[0] if full_name else "there"
    text_body = (
        f"Hi {first_name},\n\n"
        f"We received a request to reset your AI Marketing Agent password. "
        f"Reset it here:\n\n{reset_url}\n\n"
        f"This link expires in 30 minutes. If you didn't request this, you "
        f"can safely ignore this email — your password won't be changed.\n"
    )
    html_body = f"""\
<div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
  <p>Hi {first_name},</p>
  <p>We received a request to reset your AI Marketing Agent password.</p>
  <p><a href="{reset_url}" style="display:inline-block;background:#12161F;color:#fff;
     padding:10px 20px;border-radius:6px;text-decoration:none;">Reset password</a></p>
  <p style="color:#7C89A3;font-size:13px;">This link expires in 30 minutes. If you didn't
     request this, you can safely ignore this email — your password won't be changed.</p>
</div>
"""
    return EmailContent(
        to=to,
        subject="Reset your password — AI Marketing Agent",
        text_body=text_body,
        html_body=html_body,
    )
