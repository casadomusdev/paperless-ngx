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


# RKC: Recipient domain verification — DNS MX and optional SMTP port probe (v1.2.9)
def verify_recipient_domain(address: str, level: str = "dns") -> tuple[bool, str]:
    """
    Verify that an email address's domain can receive mail.

    Level 'dns':      Check that the domain has at least one MX record (2s timeout).
    Level 'dns+smtp': Also probe port 25 on the first MX host (4s connect timeout).
                      - Connection refused → hard fail (no server listening)
                      - Timeout → inconclusive, logs warning, returns True (don't block send)
                      - Connected → pass (banner optional)

    Returns:
        (ok, reason) — ok=True means verification passed or was inconclusive.
    """
    if "@" not in address:
        return False, f"Cannot extract domain from address '{address}'"
    domain = address.split("@", 1)[1].lower()

    # --- DNS MX check ---
    try:
        import dns.resolver
        import dns.exception
        answers = dns.resolver.resolve(domain, "MX", lifetime=2.0)
        mx_records = sorted(answers, key=lambda r: r.preference)
        if not mx_records:
            return False, f"No MX records found for domain '{domain}'"
        mx_host = str(mx_records[0].exchange).rstrip(".")
    except ImportError:
        return True, "dnspython not available — DNS check skipped"
    except dns.resolver.NXDOMAIN:
        return False, f"Domain '{domain}' does not exist (NXDOMAIN)"
    except dns.resolver.NoAnswer:
        return False, f"No MX records found for domain '{domain}'"
    except dns.exception.Timeout:
        return False, f"DNS lookup timed out for domain '{domain}'"
    except Exception as e:
        return False, f"DNS lookup failed for domain '{domain}': {e}"

    if level != "dns+smtp":
        return True, f"MX record found for '{domain}': {mx_host}"

    # --- SMTP port 25 probe ---
    import socket
    try:
        conn = socket.create_connection((mx_host, 25), timeout=4.0)
        banner = ""
        try:
            conn.settimeout(2.0)
            banner_bytes = conn.recv(512)
            banner = banner_bytes.decode("ascii", errors="replace").strip()
        except Exception:
            pass
        try:
            conn.sendall(b"QUIT\r\n")
        except Exception:
            pass
        conn.close()
        if banner:
            return True, f"SMTP server at {mx_host}:25 responding (banner: {banner[:80]})"
        return True, f"SMTP server at {mx_host}:25 is listening"
    except ConnectionRefusedError:
        return False, f"SMTP connection refused at {mx_host}:25 — no mail server listening on this port"
    except socket.timeout:
        logger.warning(
            f"SMTP port 25 probe timed out for {mx_host} — outbound port 25 may be blocked. "
            f"Consider PAPERLESS_MAIL_VERIFY_RECIPIENT=dns if timeouts persist.",
        )
        return True, f"SMTP probe timed out for {mx_host}:25 (inconclusive — proceeding with send)"
    except OSError as e:
        logger.warning(f"SMTP port 25 probe error for {mx_host}: {e} — treating as inconclusive")
        return True, f"SMTP probe error for {mx_host}:25: {e} (inconclusive — proceeding with send)"
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
