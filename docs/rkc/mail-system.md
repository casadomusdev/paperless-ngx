# Mail System Enhancements

Comprehensive mail system overhaul: universal SMTP sending, Microsoft Graph API integration, multi-mailbox support, OAuth2 email sending, connection pooling, smart correspondent matching, email metadata capture, and processed mail UI improvements.

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM` | Integer | `6` | Matching algorithm for mail-created correspondents (6=Auto) |
| `PAPERLESS_MAIL_UID_FIELD` | String | `"Mail UID"` | Custom field name for IMAP UID |
| `PAPERLESS_MAIL_FROM_FIELD` | String | `"Mail From"` | Custom field name for sender email |
| `PAPERLESS_MAIL_SENDER_FIELD` | String | `"Mail Sender"` | Custom field name for sender display name |
| `PAPERLESS_MAIL_SUBJECT_FIELD` | String | `"Mail Subject"` | Custom field name for email subject |
| `PAPERLESS_MAIL_DATE_FIELD` | String | `"Mail Date"` | Custom field name for received date |
| `PAPERLESS_MAIL_SEND_SUCCESS_TAG_ID` | Int | None | Tag ID to apply when workflow email sends successfully |
| `PAPERLESS_MAIL_SEND_FAILURE_TAG_ID` | Int | None | Tag ID to apply when workflow email fails to send |
| `PAPERLESS_MAIL_SEND_ADD_NOTE` | Bool | `false` | Attach a system note on every send attempt with timestamp, recipients, and OK/FAILED status |
| `PAPERLESS_MAIL_VERIFY_RECIPIENT` | String | `"dns"` | Recipient domain verification level: `"none"` (off), `"dns"` (MX check), or `"dns+smtp"` (MX + port 25 probe) |


## Architecture Overview

```
Mail Account Types:
├── Outlook OAuth → Graph API (sending + receiving)
├── Gmail OAuth → SMTP/XOAUTH2 (sending) + IMAP (receiving)
└── Traditional → SMTP (sending) + IMAP (receiving)

Sending Priority Chain:
1. MailAccount-based sending (OAuth2 or traditional SMTP)
2. Environment variable SMTP fallback (PAPERLESS_EMAIL_*)
```

## 1. Universal SMTP Sending (v1.0.18 → v1.1.0)

### MailAccount Model Extensions
Added comprehensive SMTP fields: `smtp_server`, `smtp_port`, `smtp_security`, `smtp_username`, `smtp_password`, `use_for_sending`, `from_address`.

**Single-Account Enforcement**: When `use_for_sending=True`, automatically disables ALL other accounts via `.update()` (prevents recursive `save()` calls).

### Unified Email Backend (`mail_oauth.py`)
- `MailAccountEmailBackend()` factory returns appropriate backend based on account type
- Dual authentication: `_open_oauth()` for XOAUTH2 SASL, `_open_traditional()` for username/password
- Server defaults: Gmail (`smtp.gmail.com:587`), Outlook (`smtp.office365.com:587`)
- Graceful degradation through multiple fallback layers

### API Serialization
- SMTP password obfuscated in responses (shows `***` if set)
- `sending_account_info` read-only field showing which account was disabled when enabling current one

### Migration
`src/paperless_mail/migrations/0031_add_smtp_fields.py` — adds 6 new fields to MailAccount model.

## 2. Microsoft Graph API Integration (v1.1.0)

### Why Graph API?
Microsoft 365 Security Defaults block SMTP AUTH protocol entirely (even with OAuth2). Graph API bypasses this restriction.

### Graph API Sending (`mail_graph.py`)
- `OutlookGraphEmailBackend` class using `POST /v1.0/users/{username}/sendMail`
- Full support: HTML/text content, attachments (base64), CC, BCC, reply-to, custom from address
- Automatic OAuth token refresh before sending
- Structured JSON error responses (better than SMTP status codes)
- **Shared mailbox Sent Items**: when `from_email` differs from the account's own username, `_get_send_endpoint()` scopes the `sendMail` call to the shared mailbox's user endpoint (`/users/{from_email}/sendMail`). Graph API then deposits the Sent Items copy in the shared mailbox's Sent folder instead of the sending account's. Requires `Mail.Send.Shared` scope (already present) and Exchange "Send As" permission on the shared mailbox.

### Graph API Retrieval (`mail_graph_retrieval.py`)
- Uses `/v1.0/users/{username}/messages` endpoint
- **Critical**: `$orderby: 'receivedDateTime asc'` (oldest first) for chronological ingestion
- Email field fallback: checks both `from` and `sender` fields (Graph API sometimes omits `from`)
- S/MIME attachment filtering: filters `smime.p7s`, `smime.p7m` and related content types

### OAuth Scope Changes (`oauth.py`)
Changed from `https://outlook.office.com/SMTP.Send` to `https://graph.microsoft.com/Mail.Send`. Existing accounts require re-authorization.

## 3. Multi-Mailbox Support (v1.1.0)

### Endpoint Migration
Changed ALL Graph API methods (8 total) from `/me/` to `/users/{self.mail_account.username}/`:
- `fetch_messages()`, `get_attachments()`, `mark_message_read()`, `delete_message()`, `flag_message()`, `move_message()`, `tag_message()`, `_get_folder_id()`

### OAuth Scopes
Added `Mail.Read.Shared` and `Mail.ReadWrite.Shared` for delegated mailbox access.

### Configuration
- Personal mailbox: `username=user@company.com`
- Shared mailbox: `username=shared@company.com`
- Requires Exchange "Full Access" permission for shared mailboxes

## 4. Connection Pooling (v1.0.17)

### Problem
Celery chord pattern created 100s of simultaneous OAuth2 authentication requests, triggering Microsoft IMAP rate limiting.

### Solution
- Modified `queue_consumption_tasks()` to create `PENDING_POST_ACTION` entries instead of immediate callbacks
- Created `process_pending_mail_actions()` scheduled task via Celery Beat
- One pooled IMAP connection per account per batch
- Uses `PAPERLESS_EMAIL_TASK_CRON` schedule (default: `*/10 * * * *`)

## 5. Smart Correspondent Matching (v1.0.27)

### FROM_SMART Mode
Added `FROM_SMART` mode (value 5) to `CorrespondentSource` enum. Creates correspondents in RFC 5322 format: `"Sender Name <sender@email.com>"`.

### Three-Tier Matching Strategy
1. **Exact match**: Find correspondent with exact name
2. **Email extraction match**: Extract email from `<brackets>` and compare (case-insensitive)
3. **Create new**: Create correspondent in smart format

### Examples
- Existing: `"Accounts <accounts@company.com>"` + Incoming: `"John <accounts@company.com>"` → Match (email matches)
- Admin renames to: `"Company.com Accounts <accounts@company.com>"` + Next mail → Still matches
- New sender `"New <new@example.com>"` → Creates new correspondent

### Correspondent Matching Algorithm (v1.0.28)
Fixed inconsistency where mail-created correspondents used `MATCH_ANY` (1) while UI-created ones used `MATCH_AUTO` (6). Configurable via `PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM`.

## 6. Email Metadata Custom Fields (v1.0.12 → v1.0.26)

### Captured Fields
| Field | Type | Env Var | Description |
|-------|------|---------|-------------|
| Mail UID | STRING | `PAPERLESS_MAIL_UID_FIELD` | IMAP unique identifier |
| Mail From | STRING | `PAPERLESS_MAIL_FROM_FIELD` | Sender email address |
| Mail Sender | STRING | `PAPERLESS_MAIL_SENDER_FIELD` | Sender display name |
| Mail Subject | STRING | `PAPERLESS_MAIL_SUBJECT_FIELD` | Email subject line |
| Mail Date | DATE | `PAPERLESS_MAIL_DATE_FIELD` | Received date (YYYY-MM-DD) |

### Implementation
- `ConsumableDocument` dataclass extended with 5 optional fields
- Consumer helper `_attach_mail_metadata_custom_fields()` creates `CustomField` definitions on first run, then `CustomFieldInstance` for each document
- Triggered on `mailrule_id` (not on individual field values) — all five fields are always written for every mail-sourced document
- **Mandatory for all five fields**: string fields store `""` when the value is absent so templates never encounter a missing key; date fields store `NULL`
- **Truncation of long values**: `CustomFieldInstance.value_text` has `max_length=128`. A value exceeding this causes a `DataError` that aborts the entire `transaction.atomic()` block, leaving **all** fields missing (not just the offending one). The `_truncate_text_field()` helper truncates to 127 chars + `"…"` when needed; a WARNING is logged so the event is visible in the paperless consumer log
- Called immediately after `_store()` creates the document row, **before** `document_consumption_finished.send()` and `document.save()` — ensuring filename/storage-path templates that reference these fields (e.g. `{{ custom_fields["Mail Betreff"].value }}`) always resolve correctly
- Non-critical: failures log warnings without aborting consumption

### Why All Fields Must Be Created Unconditionally
Filename and storage-path templates are rendered as part of `generate_unique_filename()`, which is called just before and again inside `document.save()`. If any of these custom fields are referenced in a template but the `CustomFieldInstance` does not yet exist, Jinja2 raises a key/attribute error that propagates out of the transaction and causes the entire document ingestion to fail with `'dict' object has no attribute '<field-name>'`. Creating all five fields upfront (including empty-value ones) prevents this regardless of email content.

### Querying by Mail UID
```
GET /api/documents/?custom_field_query=["Mail UID", "exact", "12345"]
```

## 7. Process All Mails Action (v1.0.19)

Added `PROCESS_ALL` action (value 6) to `MailAction` enum. Processes ALL matching mails (read or unread) without modifying mail state. Each mail still only processed once via `ProcessedMail` UID tracking.

Use cases: archive folders, shared mailboxes, bulk processing existing mail archives.

## 8. Processed Mail UI Enhancements (v1.0.13–v1.0.24)

### Pagination Fix (v1.0.13)
Fixed `ngb-pagination` using `processedMails.length` instead of total count from API.

### Error Modal (v1.0.14)
- 20-char preview in table, hover popover for full text, click opens scrollable modal
- Changed date columns from `longDate` to `short` (includes time)

### Filtering (v1.0.15 → v1.0.16)
- Started as client-side filtering (v1.0.15), migrated to server-side (v1.0.16)
- Filter fields: Error, Subject, Received, Processed, Mail UID
- Django ORM `__icontains` for case-insensitive database search
- Debounced input (100ms, 3-char minimum)

### Mail UID Column (v1.0.20)
Added Mail UID as first visible data column, searchable via filter dropdown.

### Select All in Database (v1.0.24)
- Header checkbox → selects page → banner offers "Select all Y items" in database
- Filter-aware deletion with confirmation dialogs showing counts
- Backend `bulk_delete` endpoint supports `delete_all` with filter parameters

## 9. Email Date as Document Created Date (v1.2.2)

When consuming emails (both attachments and `.eml` files), Paperless now sets the document's `created` date from the email's `Date:` header rather than leaving it to the OCR content parser or defaulting to today.

### Behaviour
- Both `_process_attachments()` and `_process_eml()` now pass `created=` in `DocumentMetadataOverrides`
- The value is `message.date` (a `datetime.datetime`), timezone-normalized via `make_aware()` if naive
- If `message.date` is `None` (malformed email), the field is omitted and normal fallback logic applies
- The override feeds into `signals/handlers.py` which applies it to the document's `created` field before save

### Why This Matters
Previously all mail-consumed documents had their `created` date set to either the date inferred from OCR text or the consumption date — whichever the document parser picked. A PDF invoice received by email on 2024-01-15 would appear in Paperless with a random OCR-guessed date or today's date.  Now it reliably appears with the date the email arrived.

### Implementation
Two lines added to `mail.py`, one in each of the `DocumentMetadataOverrides()` constructor calls:
```python
created=(make_aware(message.date) if is_naive(message.date) else message.date) if message.date else None,
```

## 10. UI/UX Enhancements (v1.1.0)

### Mail Account Edit Dialog
- Split into "Receiving (IMAP)" and "Sending (SMTP)" sections
- OAuth accounts show info box explaining XOAUTH2 (hide credentials)
- Traditional accounts show full SMTP credential fields
- `onSendingToggle()` auto-populates default SMTP settings

### Visual Indicators
- Send-fill icon badge on accounts where `use_for_sending=true`
- Info message when SMTP is configured via env vars but no sending account is set
- Bootstrap tooltip styling fix: `::ng-deep .tooltip-inner { color: white !important; }` for dark mode

### Enhanced Log Messaging
Changed "No rules enabled for account..." to clarify that send-only accounts don't require rules.

## Critical Implementation Gotchas

| Issue | Impact if Missed | Solution |
|-------|-----------------|----------|
| Graph API `from` field sometimes missing | Emails marked processed but never ingested (data loss) | Check both `from` and `sender` fields with fallback |
| Email ordering | Confusing document display order | Use `receivedDateTime asc` (oldest first) |
| S/MIME attachments | Unwanted "smime" documents for every signed email | Filter by content type AND filename |
| Single-account enforcement | Recursive `save()` infinite loop | Use `.update()` when disabling other accounts |
| Multi-mailbox endpoints | Username field ignored, wrong mailbox accessed | ALL 8 Graph API methods must use `/users/{username}/` not `/me/` |
| Shared mailbox Sent Items | Sent Items land in sending account, not shared mailbox | Call `sendMail` on the shared mailbox's user endpoint, not the sending account's |
| SMTP password in API | Security: password exposed in plain text | Obfuscate in serializer responses |

## Files Modified

### Backend — Core Mail System
- `src/paperless_mail/models.py` — MailAccount model extensions, FROM_SMART enum, PROCESS_ALL action
- `src/paperless_mail/migrations/0031_add_smtp_fields.py` — SMTP fields migration
- `src/paperless_mail/mail_oauth.py` — Unified `MailAccountEmailBackend`, factory function
- `src/paperless_mail/serialisers.py` — SMTP fields, password obfuscation
- `src/paperless_mail/mail.py` — Smart correspondent matching, connection pooling, metadata extraction, process all action
- `src/paperless_mail/filters.py` — Server-side filtering for processed mail
- `src/paperless_mail/views.py` — Enhanced bulk_delete
- `src/paperless_mail/tasks.py` — Enhanced log messaging
- `src/documents/mail.py` — Unified email sending backend integration
- `src/documents/data_models.py` — ConsumableDocument metadata fields
- `src/documents/consumer.py` — Mail metadata custom field attachment

### Backend — Graph API
- `src/paperless_mail/mail_graph.py` — Graph API sending backend (NEW)
- `src/paperless_mail/mail_graph_retrieval.py` — Graph API retrieval with multi-mailbox support
- `src/paperless_mail/oauth.py` — Updated OAuth scopes

### Backend — Configuration
- `src/paperless/settings.py` — All mail-related environment variables, Celery Beat schedule
- `src/documents/views.py` — UI settings exposure

### Frontend
- `src-ui/src/app/data/mail-account.ts` — SMTP fields, use_for_sending, from_address
- `src-ui/src/app/data/mail-rule.ts` — FromSmart enum value
- `src-ui/src/app/data/ui-settings.ts` — SMTP_ENV_CONFIGURED, MAIL_CORRESPONDENT_MATCHING_ALG keys
- `src-ui/src/app/components/manage/mail/mail.component.ts` — Current sending account indicator
- `src-ui/src/app/components/manage/mail/mail.component.html` — Sending badges, env var info
- `src-ui/src/app/components/common/edit-dialog/mail-account-edit-dialog/` (ts + html) — IMAP/SMTP split, OAuth info
- `src-ui/src/app/components/manage/mail/processed-mail-dialog/` (ts + html) — All processed mail UI enhancements
- `src-ui/src/app/services/rest/processed-mail.service.ts` — bulk_delete_filtered
- `src-ui/src/styles.scss` — Tooltip dark mode fix
- `src-ui/src/app/components/common/edit-dialog/correspondent-edit-dialog/` — Settings-based matching default

### Documentation
- `MS365_OAUTH_SETUP.md` — Microsoft 365 OAuth setup guide

## Migration Guide for Existing Deployments

### Outlook OAuth Accounts
Re-authorization required for new scopes (`Mail.Send`, `Mail.Read`, `Mail.Send.Shared`). Process: Settings > Mail > Mail Accounts > Click OAuth button again. Mail receiving switches from IMAP to Graph API.

### Shared Mailbox Support
Set SMTP From field to shared mailbox email. User must have Send As/Send on Behalf permissions in Exchange.

### Environment Variable Fallback
`PAPERLESS_EMAIL_*` variables continue working as fallback. Account-based sending takes priority.

## 11. S/MIME Signed Message Support (v1.2.3 + v1.2.4)

### Background: Two S/MIME Signing Variants

S/MIME defines two ways to digitally sign an email. Both are transparent to the Outlook user (both show "This message has a digital signature") but produce very different MIME structures:

| Variant | MIME type | Blob file | Structure |
|---------|-----------|-----------|-----------|
| **Detached** | `multipart/signed` | `smime.p7s` | Original message + separate signature |
| **Opaque** | `application/pkcs7-mime; smime-type=signed-data` | `smime.p7m` | Entire message wrapped inside CMS blob |

The Microsoft Graph API attachments endpoint surfaces the S/MIME wrapper as an attachment but does **not** expose the real file attachments inside. This caused paperless to log "Returning 0 legitimate attachments" even though PDFs were visible in Outlook.

### Detached Signing (v1.2.3) — smime.p7s

**Detection**: Any attachment with `pkcs7-signature`/`x-pkcs7-signature` content type, or filename `smime.p7s`.

**Extraction flow**:
1. Fetch raw MIME via `GET /messages/{id}/$value`
2. Parse with Python's `email.message_from_bytes()`
3. Walk MIME tree, extract `Content-Disposition: attachment` parts
4. Skip signature parts (`pkcs7-signature` content type, `smime*` filenames)
5. Return `GraphMailAttachment` objects for normal processing

No certificates required — signature verification is skipped entirely.

### Opaque Signing (v1.2.4) — smime.p7m

**Detection**: Any attachment with `pkcs7-mime`/`x-pkcs7-mime` content type where `enveloped-data` is NOT in the content type (which would indicate encryption, not signing).

**Extraction flow**:
1. Decode `contentBytes` from the attachment (already in Graph API response — no extra API call)
2. Write DER blob to a temp file
3. Run `openssl cms -verify -noverify -inform DER -in {tmp}` — `-noverify` skips certificate validation entirely
4. If DER fails, retry with `-inform PEM` (some senders produce base64-armoured blobs)
5. Parse the extracted inner MIME bytes with `_parse_mime_for_attachments()`
6. Delete temp file, return `GraphMailAttachment` objects

**Requirement**: OpenSSL binary must be available in the container (it is in the standard paperless-ngx image).

### Shared Helper: `_parse_mime_for_attachments(mime_bytes)`

Both extraction paths share a common MIME walking helper that:
- Parses byte string as MIME with `email.message_from_bytes()`
- Selects only `Content-Disposition: attachment` parts
- Skips S/MIME crypto parts (`pkcs7-signature`, `pkcs7-mime`, etc.)
- Skips parts with `smime` in the filename
- Collects `GraphMailAttachment` objects (with base64-encoded payload)

### Behavior Summary

- **No certificate required for either variant** — both paths bypass signature verification
- **Transparent to consumer** — extracted attachments appear identical to regular attachments
- **Preserves metadata** — filename, content type, and size from MIME headers
- **Temp file cleanup** — always performed in `finally` block even if OpenSSL fails
- **Graceful degradation** — if OpenSSL is missing or CMS unwrap fails, logs an error and returns 0 attachments (email is still processed without attachments, not crashed)

### S/MIME Encrypted Messages

**Not supported.** Encrypted messages (`pkcs7-mime` with `smime-type=enveloped-data`) require the recipient's private key for decryption. The detection logic explicitly excludes `enveloped-data` content types, so encrypted messages fall through to the existing v1.1.0 filter which skips the smime blob and returns 0 attachments.

Future implementation would require recipient S/MIME certificate + private key and is not on the current roadmap.

---

## 12. Recipient Domain Verification (v1.2.9)

Before sending a workflow email action, Paperless can verify that the recipient domain(s) are deliverable. Three levels are available:

| Level | Setting | Behaviour |
|-------|---------|-----------|
| **Off** | `none` | Skip verification entirely — send unconditionally |
| **DNS** (default) | `dns` | Look up MX records for each recipient domain (2s timeout). Fails if the domain has no MX records, does not exist, or the lookup times out |
| **DNS + SMTP** | `dns+smtp` | DNS check **plus** a TCP connection probe to port 25 on the first MX host (4s connect timeout). See semantics below |

Verification applies to **all** recipient addresses: TO, CC, and BCC. Duplicate domains are deduplicated (each domain is only checked once per email action).

### SMTP Port 25 Probe Semantics (`dns+smtp`)

Port 25 is the only port used by MX records for inbound mail delivery. Ports 587 (submission) and 465 (SMTPS) are for outbound mail clients connecting to their own server — they are not relevant for verifying that a recipient domain can receive mail.

| TCP outcome | Result | Behaviour |
|-------------|--------|-----------|
| **Connected** (with or without banner) | ✓ Pass | Email is sent |
| **Connection refused** (TCP RESET) | ✗ Fail | Hard block — no server listening on port 25 |
| **Timeout** | ⚠ Inconclusive | Warning logged, email **is** sent (don't block on blocked ports) |
| **Other OS error** | ⚠ Inconclusive | Warning logged, email **is** sent |

Timeout behaviour is intentionally lenient. Many VPS and cloud providers (Hetzner, AWS EC2, DigitalOcean, etc.) block outbound port 25 by default. A timeout in that environment does not prove the recipient domain can't receive mail — it just means you can't probe it from this server.

### On Failure

When verification fails (hard fail only — DNS NXDOMAIN, no MX, connection refused):

1. The email is **not sent**
2. An `ERROR` entry is written to the log with the per-address failure reasons
3. If a workflow `error_tag` is configured, it is added to `doc_tag_ids` (picked up by the enclosing `document.tags.set()` call)
4. If `PAPERLESS_MAIL_SEND_ADD_NOTE=yes`, a system note is attached to the document:
   ```
   [2025-01-15T14:30:00] Mail not sent — recipient verification failed: user@bad-domain.com: Domain 'bad-domain.com' does not exist (NXDOMAIN)
   ```

### Admin Check: Is Outbound Port 25 Available?

Run the provided helper script from inside the paperless worker container:

```bash
# From outside the container:
docker exec <paperless-worker> python3 /opt/paperless/scripts/check_smtp_port25.py

# Test against a specific MX host:
docker exec <paperless-worker> python3 /opt/paperless/scripts/check_smtp_port25.py alt1.gmr-smtp-in.l.google.com
```

**Exit codes:**
- `0` — Port 25 is reachable → `PAPERLESS_MAIL_VERIFY_RECIPIENT=dns+smtp` will work
- `1` — Connection refused → TCP RESET from firewall or no server
- `2` — Timeout → outbound port 25 is **blocked** by your provider. Options:
  - Contact provider to unblock (may require account verification)
  - Keep `PAPERLESS_MAIL_VERIFY_RECIPIENT=dns` (the default) — skips the port probe
- `3` — Other network error

### Configuration

```bash
# Default — DNS MX check only (fast, passive, no connection to target)
PAPERLESS_MAIL_VERIFY_RECIPIENT=dns

# Opt-in to also probe port 25 (adds ~4s per unique domain)
PAPERLESS_MAIL_VERIFY_RECIPIENT=dns+smtp

# Disable entirely
PAPERLESS_MAIL_VERIFY_RECIPIENT=none
```

### Implementation

- `verify_recipient_domain(address, level)` in `src/documents/mail.py` — standalone function, catches all exceptions
- Called from `email_action()` in `src/documents/signals/handlers.py` **after** address validation and **before** the send attempt
- `dnspython>=2.7` required (added to `pyproject.toml`)
- Admin port check script: `scripts/check_smtp_port25.py`

---

## Version History

- **v1.2.9**: Recipient domain verification for workflow emails — DNS MX check (default) with optional SMTP port 25 probe; admin check script at `scripts/check_smtp_port25.py`
- **v1.2.8**: Mail send feedback — success/failure tags and optional system note on workflow email send attempts (both SMTP and Graph API paths)

- **v1.2.7**: Shared mailbox Sent Items — `sendMail` endpoint scoped to shared mailbox when `from_email` differs from account username
- **v1.2.4**: Opaque S/MIME signed message support (smime.p7m) via OpenSSL CMS unwrap; shared MIME walking helper
- **v1.2.3**: Detached S/MIME signed message support (smime.p7s) via raw MIME $value fetch
- **v1.0.12**: Mail-document correlation via IMAP UID custom field
- **v1.0.13**: Processed mail pagination fix
- **v1.0.14**: Error modal & date+time columns in processed mail
- **v1.0.15**: Client-side processed mail filtering
- **v1.0.16**: Server-side processed mail filtering
- **v1.0.17**: Connection pooling for mail actions
- **v1.0.18**: OAuth2 email sending support
- **v1.0.19**: "Process all mails" action
- **v1.0.20**: Mail UID column in processed mail
- **v1.0.24**: "Select all in database" for processed mail
- **v1.0.26**: Email metadata custom fields (From, Sender, Subject, Date)
- **v1.0.27**: Smart correspondent matching (FROM_SMART)
- **v1.0.28**: Correspondent matching algorithm fix
- **v1.1.0**: Universal SMTP, Graph API integration, multi-mailbox, UI/UX overhaul
- **v1.2.2**: Email `Date:` header used as document `created` date for all mail-consumed documents
