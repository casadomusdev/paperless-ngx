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


# RKC: Shared helpers for recipient verification and send feedback (v1.3.0)
def check_recipient_addresses(
    to_list: list[str],
    cc_list: list[str],
    bcc_list: list[str],
    level: str,
) -> list[str]:
    """
    Run verify_recipient_domain() on all unique domains across TO, CC, and BCC.
    Returns a list of failure strings; empty list means all addresses passed.
    """
    failures: list[str] = []
    checked_domains: dict[str, tuple[bool, str]] = {}
    for addr in to_list + cc_list + bcc_list:
        domain = addr.split("@", 1)[1].lower() if "@" in addr else None
        if domain and domain in checked_domains:
            ok, reason = checked_domains[domain]
        else:
            ok, reason = verify_recipient_domain(addr, level=level)
            if domain:
                checked_domains[domain] = (ok, reason)
        logger.info(
            f"Recipient verification [{level}] {addr}: {'PASS' if ok else 'FAIL'} — {reason}",
        )
        if not ok:
            failures.append(f"{addr}: {reason}")
    return failures


def create_mail_send_note(
    document,
    to_str: str,
    success: bool,
    error_msg: str | None = None,
    user=None,
    webhook_note: str | None = None,
) -> None:
    """
    Attach a system note to the document recording the mail send outcome.
    Logs a warning if note creation fails but does not raise.
    """
    from django.utils import timezone as tz
    from documents.models import Note
    _ts = tz.localtime(tz.now()).strftime("%Y-%m-%dT%H:%M:%S")
    if success:
        note_text = f"[{_ts}] Mail to {to_str} — OK"
    else:
        note_text = (
            f"[{_ts}] Mail to {to_str} — FAILED: {error_msg}"
            if error_msg
            else f"[{_ts}] Mail to {to_str} — FAILED"
        )
    # RKC: Append webhook outcome as second line when configured (v1.4.0)
    if webhook_note is not None:
        note_text += f"\n  Webhook \u2192 {webhook_note}"
    # /end RKC edit
    try:
        Note.objects.create(note=note_text, document=document, user=user)
    except Exception as e:
        logger.warning(f"Could not create mail send note for document '{document}': {e}")


def create_mail_verify_fail_note(document, failure_summary: str, user=None) -> None:
    """
    Attach a system note recording a recipient verification failure.
    Logs a warning if note creation fails but does not raise.
    """
    from django.utils import timezone as tz
    from documents.models import Note
    _ts = tz.localtime(tz.now()).strftime("%Y-%m-%dT%H:%M:%S")
    note_text = f"[{_ts}] Mail not sent — recipient verification failed: {failure_summary}"
    try:
        Note.objects.create(note=note_text, document=document, user=user)
    except Exception as e:
        logger.warning(f"Could not create mail verification failure note for document '{document}': {e}")
# /end RKC edit


# RKC: POST all sent-email data to a configurable webhook endpoint (v1.4.0)
def fire_mail_send_webhook(
    email: EmailMessage,
    doc_id_map: dict[str, int | None] | None = None,
) -> str | None:
    """Fire a POST request to the configured webhook URL after a successful email send.

    Builds a JSON payload with all email fields and base64-encoded attachments,
    then POSTs it with an optional auth header.  Returns a short status string
    on success or failure so callers can include it in document notes.
    Returns None immediately when no webhook URL is configured.

    doc_id_map: optional mapping of attachment filename → Paperless document pk.
    When provided, each attachment entry in the payload includes a 'document_id'
    field (integer or null for pre-consumption / non-document attachments).
    """
    import base64
    import httpx
    from email.message import Message as RawEmailMessage

    webhook_url = getattr(settings, "MAIL_SEND_WEBHOOK_URL", "")
    if not webhook_url:
        return None

    _doc_id_map: dict[str, int | None] = doc_id_map or {}

    # Build attachments list — handle both raw bytes and parsed RFC-822 Message objects
    attachments_payload = []
    for att_filename, att_content, att_mime in getattr(email, "attachments", []):
        try:
            if isinstance(att_content, RawEmailMessage):
                att_bytes = att_content.as_bytes()
            elif isinstance(att_content, bytes):
                att_bytes = att_content
            elif isinstance(att_content, str):
                att_bytes = att_content.encode("utf-8", errors="replace")
            else:
                att_bytes = b""
            attachments_payload.append({
                "document_id": _doc_id_map.get(att_filename),
                "filename": att_filename or "",
                "mime_type": att_mime or "",
                "content": base64.b64encode(att_bytes).decode("ascii"),
            })
        except Exception as exc:
            logger.warning(
                f"Mail send webhook: could not encode attachment '{att_filename}': {exc}",
            )
            attachments_payload.append({
                "document_id": _doc_id_map.get(att_filename),
                "filename": att_filename or "",
                "mime_type": att_mime or "",
                "content": "",
            })

    payload = {
        "from": email.from_email or "",
        "to": list(email.to) if email.to else [],
        "cc": list(email.cc) if email.cc else [],
        "bcc": list(email.bcc) if email.bcc else [],
        "subject": email.subject or "",
        "body": email.body or "",
        "is_html": getattr(email, "content_subtype", "plain") == "html",
        "attachments": attachments_payload,
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = getattr(settings, "MAIL_SEND_WEBHOOK_TOKEN", "")
    token_header = getattr(settings, "MAIL_SEND_WEBHOOK_TOKEN_HEADER", "Authorization")
    if token:
        headers[token_header] = token

    try:
        resp = httpx.post(webhook_url, json=payload, headers=headers, timeout=10.0)
        status = f"OK (HTTP {resp.status_code})"
        logger.debug(f"Mail send webhook: POST to {webhook_url} → {resp.status_code}")
        return status
    except Exception as exc:
        reason = str(exc)
        logger.warning(f"Mail send webhook: POST to {webhook_url} failed: {reason}")
        return f"FAILED: {reason}"
# /end RKC edit


@dataclass(frozen=True)
class EmailAttachment:
    path: Path
    mime_type: str
    friendly_name: str
    document_id: int | None = None


def _build_email_message(
    subject: str,
    body: str,
    to: list[str],
    attachments: list[EmailAttachment],
    from_email: str | None,
    cc: list[str] | None,
    bcc: list[str] | None,
    is_html: bool,
) -> EmailMessage:
    """Build a Django EmailMessage with attachments from the given parameters."""
    mail_account = get_sending_mail_account()

    if mail_account:
        logger.debug(f"Using mail account '{mail_account.name}' for sending email")
        sender = from_email if from_email else get_from_address(mail_account)
        email = EmailMessage(
            subject=subject, body=body, from_email=sender,
            to=to, cc=cc or [], bcc=bcc or [],
        )
        email.connection = MailAccountEmailBackend(mail_account)
    else:
        logger.debug("Using environment variable SMTP configuration for sending email")
        email = EmailMessage(
            subject=subject, body=body, from_email=from_email,
            to=to, cc=cc or [], bcc=bcc or [],
        )

    if is_html:
        email.content_subtype = "html"

    used_filenames: set[str] = set()
    with FileLock(settings.MEDIA_LOCK):
        for attachment in attachments:
            filename = _get_unique_filename(attachment.friendly_name, used_filenames)
            used_filenames.add(filename)
            with attachment.path.open("rb") as f:
                content = f.read()
                if attachment.mime_type == "message/rfc822":
                    content = message_from_bytes(content)
                email.attach(filename=filename, content=content, mimetype=attachment.mime_type)

    return email


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
    retries: int = 2,
) -> tuple[int, str | None]:
    """
    Send an email with attachments.

    RKC: Enhanced to support mail account SMTP authentication (v1.1.0).
    RKC: Added from_email, cc, bcc, is_html parameters (v1.2.0).
    RKC: Inline retry with exponential backoff for transient failures (v1.5.0).
         On each retry a fresh EmailMessage is built (re-reads attachments from
         disk) because Django's SMTP backend consumes file handles on send.

    Args:
        subject: Email subject
        body: Email body text
        to: List of recipient email addresses
        attachments: List of attachments
        from_email: Optional override for sender address
        cc: Optional list of CC email addresses
        bcc: Optional list of BCC email addresses
        is_html: Whether the body contains HTML content
        retries: Number of immediate retry attempts (default 2; total 3 tries)

    Returns:
        tuple[int, str | None] — (n_sent, webhook_status)
    """
    import time as _time

    doc_id_map: dict[str, int | None] = {
        att.friendly_name: att.document_id for att in attachments
    }

    last_error: Exception | None = None
    for attempt in range(1 + retries):
        try:
            email = _build_email_message(
                subject, body, to, attachments,
                from_email, cc, bcc, is_html,
            )
            n_sent = email.send()
            webhook_status = (
                fire_mail_send_webhook(email, doc_id_map) if n_sent > 0 else None
            )
            return n_sent, webhook_status
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                delay = 2 ** (attempt + 1)  # 2s, 4s
                logger.warning(
                    f"send_email attempt {attempt + 1}/{1 + retries} failed: {exc}. "
                    f"Retrying in {delay}s..."
                )
                _time.sleep(delay)
            else:
                logger.error(
                    f"send_email failed after {1 + retries} attempts: {exc}"
                )
    # All retries exhausted — raise the last error so callers can handle it
    raise last_error  # type: ignore[misc]
# /end RKC edit


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
