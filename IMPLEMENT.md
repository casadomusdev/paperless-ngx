# IMPLEMENT.md

## GOAL

Add a mail send webhook: for every email that is sent (both workflow-triggered and manual), POST a JSON payload to a configurable webhook URL containing all relevant email fields — to, from, cc, bcc, subject, body, and all attachments base64-encoded. Optionally include an access token passed as a configurable header. If document notes are enabled (`PAPERLESS_MAIL_SEND_ADD_NOTE`), append a second line to the note recording the webhook call outcome.

## ANALYSIS

There are two places where `send_email()` is called:
1. `email_action()` in `signals/handlers.py` — workflow-triggered emails (runs in Celery task context)
2. `email_documents()` in `views.py` — manual send from UI (runs in Django request context)

Both paths call through `send_email()` in `documents/mail.py`, which is the single central dispatch point.

After `email.send()` succeeds, the `EmailMessage` object has all data in memory: `email.from_email`, `email.to`, `email.cc`, `email.bcc`, `email.subject`, `email.body`, `email.content_subtype`, and `email.attachments` (list of `(filename, content, mimetype)` tuples). The attachment content is already loaded at this point, so no extra file reads are needed.

`send_email()` currently returns `int` (number of messages sent). Changing it to return `tuple[int, str | None]` (n_sent, webhook_status) allows callers to thread the webhook outcome into the document note without any global state or separate calls.

The `create_mail_send_note()` function already exists in `mail.py` and is called by both code paths. Adding an optional `webhook_note: str | None = None` parameter lets callers append a second line to the note when the webhook is configured.

## IMPLEMENTATION

### Phase 1: Settings (settings.py)

Add 3 new env vars inside a new `# RKC:` block after the existing mail send feedback block:
- `MAIL_SEND_WEBHOOK_URL` (from `PAPERLESS_MAIL_SEND_WEBHOOK_URL`, default `""`)
- `MAIL_SEND_WEBHOOK_TOKEN` (from `PAPERLESS_MAIL_SEND_WEBHOOK_TOKEN`, default `""`)
- `MAIL_SEND_WEBHOOK_TOKEN_HEADER` (from `PAPERLESS_MAIL_SEND_WEBHOOK_TOKEN_HEADER`, default `"Authorization"`)

### Phase 2: mail.py

**`fire_mail_send_webhook(email: EmailMessage) -> str | None`**:
- Returns `None` immediately if `settings.MAIL_SEND_WEBHOOK_URL` is empty
- Builds JSON payload: `from`, `to`, `cc`, `bcc`, `subject`, `body`, `is_html`, `attachments` list
- Each attachment: `{"filename": ..., "mime_type": ..., "content": base64}` — handle `message.Message` objects (rfc822) by encoding them back to bytes first
- Fires `httpx.post()` with `timeout=10.0` and optional token header
- On success: returns `"OK (HTTP {status_code})"`
- On failure: logs warning, returns `"FAILED: {reason}"`

**`send_email()`**: Change return from `int` to `tuple[int, str | None]`. After `n = email.send()`, call `fire_mail_send_webhook(email)` when `n > 0`. Return `(n, webhook_status)`.

**`create_mail_send_note()`**: Add `webhook_note: str | None = None` parameter. When provided, append `\n  Webhook → {webhook_note}` to the note text.

### Phase 3: handlers.py (workflow path)

Unpack `n_messages, webhook_status = send_email(...)`. Pass `webhook_note=webhook_status` to `create_mail_send_note()` call.

### Phase 4: views.py (manual send path)

Unpack `n_messages, webhook_status = send_email(...)`. Pass `webhook_note=webhook_status` to the two `create_mail_send_note()` calls (success path and exception path, though the exception path won't have a webhook status — pass `None` there).

### Phase 5: Documentation

Update `RKC_CUSTOMIZATIONS.md` with new feature description, 3 new env vars in the table, and version history entry v1.4.0.
Update `docs/rkc/mail-system.md` with new env var rows and a "Mail Send Webhook" section.
