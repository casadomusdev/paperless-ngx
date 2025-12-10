from __future__ import annotations

from dataclasses import dataclass
from email import message_from_bytes
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from filelock import FileLock

# RKC: Import OAuth2 email backend support (v1.0.18)
import logging
from paperless_mail.mail_oauth import (
    get_sending_mail_account,
    get_from_address,
    OAuth2EmailBackend,
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
) -> int:
    """
    Send an email with attachments.

    RKC: Enhanced to support OAuth2 SMTP authentication if configured (v1.0.18).
    Falls back to regular SMTP if no OAuth2 account is available.

    Args:
        subject: Email subject
        body: Email body text
        to: List of recipient email addresses
        attachments: List of attachments

    Returns:
        Number of emails sent

    TODO: re-evaluate this pending https://code.djangoproject.com/ticket/35581 / https://github.com/django/django/pull/18966
    """
    # RKC: Check for OAuth2 sending account (v1.0.18)
    oauth_account = get_sending_mail_account()
    
    if oauth_account:
        # Use OAuth2 backend
        logger.debug(f"Using OAuth2 account {oauth_account.name} for sending email")
        from_email = get_from_address(oauth_account)
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=to,
        )
        
        # Set the OAuth2 backend
        email.connection = OAuth2EmailBackend(oauth_account)
    else:
        # Use regular SMTP (original behavior)
        logger.debug("Using regular SMTP for sending email")
        email = EmailMessage(
            subject=subject,
            body=body,
            to=to,
        )
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
