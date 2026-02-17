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
- Non-critical: failures log warnings without aborting consumption

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

## 9. UI/UX Enhancements (v1.1.0)

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

## Version History

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
