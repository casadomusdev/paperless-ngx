"""
RKC: Email Send Queue with Retry (v1.5.0)
Provides a persistent email queue that catches send failures and retries them
with exponential backoff.  Ensures no email is silently lost due to transient
failures (OAuth token refresh errors, Graph API timeouts, etc.).

PendingEmail stores raw Jinja2 template strings — on each retry the templates
are re-rendered with the document's current context so that custom field
updates are picked up.  Attachments are rebuilt from the document source_path
on each attempt (file content is never stored in the database).

Retry backoff: min(base_seconds * 2^attempts, max_seconds)
Defaults: base=300s (5min), max=86400s (24h), max_attempts=50 (~5 days)

Processed by Celery Beat task `process_pending_emails` running every 5 minutes
(configurable via PAPERLESS_MAIL_QUEUE_CRON).

Model: PendingEmail is defined in documents/models.py.
"""
import logging
import time
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from documents.models import Document, PendingEmail, WorkflowActionEmail

logger = logging.getLogger("paperless.mail.queue")


# ---------------------------------------------------------------------------
# Backoff Helpers
# ---------------------------------------------------------------------------

def calculate_next_retry(attempts: int) -> "timezone.datetime":
    """
    Calculate the next retry time using exponential backoff.

    Formula: min(base_seconds * 2^attempts, max_seconds)
    Defaults from settings: base=300s, max=86400s.
    """
    base = getattr(settings, "MAIL_RETRY_BASE_SECONDS", 300)
    max_interval = getattr(settings, "MAIL_RETRY_MAX_SECONDS", 86400)
    delay = min(base * (2 ** attempts), max_interval)
    return timezone.now() + timedelta(seconds=delay)
# /end RKC edit


# ---------------------------------------------------------------------------
# Enqueue Helper
# ---------------------------------------------------------------------------

def enqueue_failed_email(
    action: WorkflowActionEmail | None,
    document: Document | None,
    rendered_to: str,
    error_msg: str,
) -> PendingEmail:
    max_attempts = getattr(settings, 'MAIL_RETRY_MAX_ATTEMPTS', 50)

    if action is not None:
        pending = PendingEmail(
            action=action,
            document=document,
            subject_template=action.subject or '',
            body_template=action.body or '',
            to_template=action.to or '',
            from_template=action.from_address or '',
            cc_template=action.cc or '',
            bcc_template=action.bcc or '',
            is_html=False,
            include_document=action.include_document,
            rendered_to=rendered_to,
            max_attempts=max_attempts,
            next_retry_at=calculate_next_retry(0),
            last_error=error_msg,
            status=PendingEmail.STATUS_PENDING,
        )
    else:
        pending = PendingEmail(
            action=None,
            document=document,
            subject_template='',
            body_template='',
            to_template=rendered_to,
            from_template='',
            cc_template='',
            bcc_template='',
            is_html=False,
            include_document=True,
            rendered_to=rendered_to,
            max_attempts=max_attempts,
            next_retry_at=calculate_next_retry(0),
            last_error=error_msg,
            status=PendingEmail.STATUS_PENDING,
        )

    pending.save()
    logger.info(
        f'Queued email for retry: id={pending.pk} to={rendered_to!r} '
        f'doc={document.pk if document else chr(39)+chr(39)+None+chr(39)+chr(39)} '
        f'action={action.pk if action else chr(39)+chr(39)+manual+chr(39)+chr(39)} '
        f'next_retry={pending.next_retry_at}'
    )
    return pending
# /end RKC edit


# ---------------------------------------------------------------------------
# Celery Task: Process Pending Emails
# ---------------------------------------------------------------------------

@shared_task
def process_pending_emails():
    pending = PendingEmail.objects.pending().order_by('next_retry_at')
    count = pending.count()
    if count == 0:
        return

    logger.info(f'Processing {count} pending email(s)')

    for pe in pending:
        _process_single_pending_email(pe)
        time.sleep(1)


def _process_single_pending_email(pe: PendingEmail):
    from django.contrib.auth.models import User
    from django.core.mail import EmailMessage
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError as DjangoValidationError
    from documents.mail import (
        EmailAttachment,
        send_email,
        create_mail_send_note,
        check_recipient_addresses,
    )

    pe.status = PendingEmail.STATUS_SENDING
    pe.save(update_fields=['status', 'updated_at'])

    document = pe.document
    action = pe.action

    if document is None:
        _abandon(pe, 'Document no longer exists')
        return

    if pe.action_id is not None and action is None:
        _abandon(pe, 'Workflow action no longer exists')
        return

    try:
        if action is not None:
            _rendered = _re_render_workflow_fields(pe, action, document)
            if _rendered is None:
                return
            subject, body, to_str, from_str, cc_str, bcc_str, is_html = _rendered
        else:
            subject = pe.subject_template
            body = pe.body_template
            to_str = pe.to_template
            from_str = pe.from_template or None
            cc_str = pe.cc_template
            bcc_str = pe.bcc_template
            is_html = pe.is_html

        to_list = [a.strip() for a in to_str.split(',') if a.strip()]
        cc_list = [a.strip() for a in cc_str.split(',') if a.strip()] if cc_str else []
        bcc_list = [a.strip() for a in bcc_str.split(',') if a.strip()] if bcc_str else []

        if not to_list:
            _abandon(pe, 'No recipients after re-rendering')
            return

        all_addrs = to_list + cc_list + bcc_list
        if from_str:
            all_addrs.append(from_str)
        for addr in all_addrs:
            try:
                validate_email(addr)
            except DjangoValidationError:
                _abandon(pe, f'Invalid email address: {addr}')
                return

        verify_level = getattr(settings, 'MAIL_VERIFY_RECIPIENT', 'dns')
        if verify_level != 'none':
            failures = check_recipient_addresses(to_list, cc_list, bcc_list, verify_level)
            if failures:
                _abandon(pe, f'Recipient verification failed: {chr(59)+chr(32)}.join(failures)')
                return

        attachments = []
        if pe.include_document and document is not None:
            import pathvalidate
            from pathlib import Path
            friendly_name = pathvalidate.sanitize_filename(
                f'{document.title}{document.file_type}',
                replacement_text='-',
            )
            attachments = [
                EmailAttachment(
                    path=document.source_path,
                    mime_type=document.mime_type,
                    friendly_name=friendly_name,
                    document_id=document.id,
                )
            ]

        n_sent, _ = send_email(
            subject=subject,
            body=body,
            to=to_list,
            attachments=attachments,
            from_email=from_str,
            cc=cc_list or None,
            bcc=bcc_list or None,
            is_html=is_html,
        )

        if n_sent > 0:
            pe.status = PendingEmail.STATUS_SENT
            pe.save(update_fields=['status', 'updated_at'])
            logger.info(f'PendingEmail {pe.pk} sent successfully')

            note_user = document.owner or User.objects.filter(username='consumer').first()
            if getattr(settings, 'MAIL_SEND_SUCCESS_TAG_ID', None) is not None:
                document.tags.add(settings.MAIL_SEND_SUCCESS_TAG_ID)
            if getattr(settings, 'MAIL_SEND_FAILURE_TAG_ID', None) is not None:
                document.tags.remove(settings.MAIL_SEND_FAILURE_TAG_ID)
            if getattr(settings, 'MAIL_SEND_ADD_NOTE', False):
                create_mail_send_note(document, pe.rendered_to, True, user=note_user)
        else:
            _handle_retry(pe, 'send_email returned 0 (no messages sent)')

    except Exception as exc:
        _handle_retry(pe, str(exc))



def _re_render_workflow_fields(pe, action, document):
    from documents.templating.workflows import parse_w_workflow_placeholders
    from jinja2 import UndefinedError

    correspondent = document.correspondent.name if document.correspondent else ''
    document_type = document.document_type.name if document.document_type else ''
    owner_username = document.owner.username if document.owner else ''
    filename = document.original_filename or ''
    current_filename = document.filename or ''
    added = timezone.localtime(document.added)
    created = document.created
    title = document.title
    doc_url = f'{settings.PAPERLESS_URL}{settings.BASE_URL}documents/{document.pk}/'

    def _render(template_str):
        if not template_str:
            return ''
        return parse_w_workflow_placeholders(
            template_str, correspondent, document_type, owner_username,
            added, filename, current_filename, created, title, doc_url,
            document=document,
        )

    try:
        subject = _render(action.subject)
        body = _render(action.body)
        to_str = _render(action.to)
        from_str = _render(action.from_address)
        cc_str = _render(action.cc)
        bcc_str = _render(action.bcc)
    except UndefinedError as exc:
        _abandon(pe, f'Template references undefined variable: {exc}')
        return None

    is_html = any(
        tag in body.lower()
        for tag in ('<html', '<body', '<br', '<div', '<p>', '<table')
    ) if body else False

    return subject, body, to_str, from_str, cc_str, bcc_str, is_html


def _handle_retry(pe: PendingEmail, error_msg: str):
    from django.contrib.auth.models import User
    from documents.mail import create_mail_send_note

    pe.attempts += 1
    pe.last_error = error_msg
    logger.warning(
        f'PendingEmail {pe.pk} attempt {pe.attempts}/{pe.max_attempts} '
        f'failed: {error_msg}'
    )

    if pe.attempts >= pe.max_attempts:
        _abandon(pe, error_msg)
        return

    pe.status = PendingEmail.STATUS_PENDING
    pe.next_retry_at = calculate_next_retry(pe.attempts)
    pe.save(update_fields=[
        'status', 'attempts', 'last_error', 'next_retry_at', 'updated_at',
    ])

    if pe.attempts == 1 and pe.document is not None:
        if getattr(settings, 'MAIL_SEND_ADD_NOTE', False):
            note_user = pe.document.owner or User.objects.filter(username='consumer').first()
            from django.utils import timezone as tz
            _ts = tz.localtime(tz.now()).strftime('%Y-%m-%dT%H:%M:%S')
            note_text = (
                f'[{_ts}] Mail to {pe.rendered_to} — FAILED: {error_msg}. '
                f'Queued for retry (attempt {pe.attempts}/{pe.max_attempts}).'
            )
            from documents.models import Note
            try:
                Note.objects.create(note=note_text, document=pe.document, user=note_user)
            except Exception as e:
                logger.warning(f'Could not create retry note for PendingEmail {pe.pk}: {e}')


def _abandon(pe: PendingEmail, reason: str):
    from django.contrib.auth.models import User
    from documents.mail import create_mail_send_note

    pe.status = PendingEmail.STATUS_ABANDONED
    pe.last_error = reason
    pe.save(update_fields=['status', 'last_error', 'updated_at'])
    logger.error(
        f'PendingEmail {pe.pk} ABANDONED after {pe.attempts} attempts: {reason}'
    )

    if pe.document is not None:
        if getattr(settings, 'MAIL_SEND_FAILURE_TAG_ID', None) is not None:
            pe.document.tags.add(settings.MAIL_SEND_FAILURE_TAG_ID)
        if getattr(settings, 'MAIL_SEND_SUCCESS_TAG_ID', None) is not None:
            pe.document.tags.remove(settings.MAIL_SEND_SUCCESS_TAG_ID)
        if getattr(settings, 'MAIL_SEND_ADD_NOTE', False):
            note_user = pe.document.owner or User.objects.filter(username='consumer').first()
            create_mail_send_note(
                pe.document, pe.rendered_to, False, reason, user=note_user,
            )
# /end RKC edit
