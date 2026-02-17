from __future__ import annotations

from dataclasses import dataclass
from email import message_from_bytes
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from filelock import FileLock

# RKC: Import mail account email backend support (v1.1.0)
# Supports both OAuth2 and traditional SMTP authentication
import logging
from paperless_mail.mail_oauth import (
    get_sending_mail_account,
    get_from_address,
    MailAccountEmailBackend,
)

logger = logging.getLogger("paperless_mail")
# /end RKC edit


@dataclass(frozen=True)
class EmailAttachment:
    path: Path
    mime_type: str
    friendly_name: str


def send_email(
    subject: str,
    body: str,
    to: list[str],
    attachments: list[EmailAttachment],
    *,
    from_email: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    is_html: bool = False,
) -> int:
    """
    Send an email with attachments.

    RKC: Enhanced to support mail account SMTP authentication (v1.1.0).
    Supports both OAuth2 XOAUTH2 and traditional password authentication.
    Falls back to regular SMTP if no mail account is configured.

    RKC: Added from_email, cc, bcc, is_html parameters (v1.2.0).
    - from_email: Override sender address (priority over mail account default)
    - cc/bcc: Carbon copy / blind carbon copy recipients
    - is_html: Set content_subtype to 'html' for HTML email bodies

    Args:
        subject: Email subject
        body: Email body text
        to: List of recipient email addresses
        attachments: List of attachments
        from_email: Optional override for sender address
        cc: Optional list of CC email addresses
        bcc: Optional list of BCC email addresses
        is_html: Whether the body contains HTML content

    Returns:
        Number of emails sent

    TODO: re-evaluate this pending https://code.djangoproject.com/ticket/35581 / https://github.com/django/django/pull/18966
    """
    # RKC: Check for configured sending account (v1.1.0)
    mail_account = get_sending_mail_account()
    
    if mail_account:
        # Use mail account backend (supports both OAuth2 and traditional SMTP)
        logger.debug(f"Using mail account '{mail_account.name}' for sending email")
        # RKC: from_email priority chain (v1.2.0): explicit param → mail account default
        sender = from_email if from_email else get_from_address(mail_account)
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=sender,
            to=to,
            cc=cc or [],
            bcc=bcc or [],
        )
        
        # Set the mail account backend
        email.connection = MailAccountEmailBackend(mail_account)
    else:
        # Use regular SMTP from environment variables (original behavior)
        logger.debug("Using environment variable SMTP configuration for sending email")
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=to,
            cc=cc or [],
            bcc=bcc or [],
        )
    # /end RKC edit

    # RKC: HTML auto-detection support (v1.2.0)
    if is_html:
        email.content_subtype = "html"
    # /end RKC edit

    used_filenames: set[str] = set()

    # Something could be renaming the file concurrently so it can't be attached
    with FileLock(settings.MEDIA_LOCK):
        for attachment in attachments:
            filename = _get_unique_filename(
                attachment.friendly_name,
                used_filenames,
            )
            used_filenames.add(filename)

            with attachment.path.open("rb") as f:
                content = f.read()
                if attachment.mime_type == "message/rfc822":
                    # See https://forum.djangoproject.com/t/using-emailmessage-with-an-attached-email-file-crashes-due-to-non-ascii/37981
                    content = message_from_bytes(content)

                email.attach(
                    filename=filename,
                    content=content,
                    mimetype=attachment.mime_type,
                )

    return email.send()


def _get_unique_filename(friendly_name: str, used_names: set[str]) -> str:
    """
    Constructs a unique friendly filename for the given document, append a counter if needed.
    """
    if friendly_name not in used_names:
        return friendly_name

    stem = Path(friendly_name).stem
    suffix = "".join(Path(friendly_name).suffixes)

    counter = 1
    while True:
        filename = f"{stem}_{counter:02}{suffix}"
        if filename not in used_names:
            return filename
        counter += 1
