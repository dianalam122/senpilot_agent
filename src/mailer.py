# mailer.py
"""SMTP email sending."""

import logging
import os
import smtplib

from email.message import EmailMessage

log = logging.getLogger(__name__)


def send_email(
    to: str,
    subject: str,
    body: str,
    attachment_path: str | None = None,
) -> None:
    """Send email with optional attachment via SMTP."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    from_addr = os.environ.get("SMTP_FROM") or user

    if not all([host, user, password]):
        log.error("SMTP not configured: set SMTP_HOST, SMTP_USER, SMTP_PASS")
        raise ValueError("SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.set_content(body)

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            filename = os.path.basename(attachment_path)
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="zip",
                filename=filename,
            )
        has_attach = True
    else:
        has_attach = False

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

    log.info("Email sent to %s (attachment: %s)", to, "yes" if has_attach else "no")
