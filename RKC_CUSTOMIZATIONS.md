# RKC Customizations Documentation

This document provides a high-level inventory of all RKC customizations made to the Paperless-ngx project. Implementation details for each feature area are in [`docs/rkc/`](docs/rkc/).

All customizations are marked with `RKC:` comments throughout the codebase for easy identification. Blocks end with `# /end RKC edit` (Python), `// /end RKC edit` (TypeScript), or `<!-- /end RKC edit -->` (HTML).

## Customization Protocol

Every RKC customization must follow these conventions to ensure we can cleanly re-apply our changes after pulling upstream updates from Paperless-ngx.

### 1. Code Markers

Every code change **must** be enclosed in opening and closing RKC comments. The opening comment describes **what** the change achieves (not what it fixes). The closing comment marks the end of the block.

```python
# RKC: Ensure correspondents created from mail rules use the configured matching algorithm
correspondent, created = Correspondent.objects.get_or_create(...)
# /end RKC edit
```
```typescript
// RKC: Provide global saved views sort order for consistent sidebar display
get globalViewsSortOrder(): number[] { ... }
// /end RKC edit
```
```html
<!-- RKC: Filter button for custom field values across all data types -->
<button (click)="filterByCustomField(fieldInstance)">...</button>
<!-- /end RKC edit -->
```

### 2. Documentation Structure

Each customization is documented at **two levels**:

- **`RKC_CUSTOMIZATIONS.md`** (this file): Brief overview — what the feature does, which env vars it uses, and a link to the detail doc. One paragraph per feature, no code snippets.
- **`docs/rkc/<topic>.md`**: Full implementation details — env vars, behavior, code snippets, files modified, security model, use cases. Grouped by feature area, not by individual version. This is the reference for re-implementing the customization after an upstream merge conflict.

Every new customization or enhancement gets a **version number** in the Version History section. When a customization spans multiple versions (e.g., the mail system evolved from v1.0.12 through v1.1.0), the detail doc tracks the full evolution.

### 3. Bug Fixes vs. Features

When fixing a bug **within an RKC customization**, treat it as feature completion — not as a separate bug fix. Update the existing customization's documentation and code comments to describe the **correct behavior**, not the history of what was broken. Use language like "ensures X" or "prevents Y" rather than "fixes bug where Z". The git log is the only place that records what changed and why.

Bug fixes only get their own version entry when they address **upstream Paperless-ngx bugs** (e.g., webhook hostname validation, dashboard race condition). These are documented in [`docs/rkc/bug-fixes.md`](docs/rkc/bug-fixes.md).

---

## Table of Contents

1. [Customization Protocol](#customization-protocol)
2. [Customizations At A Glance](#customizations-at-a-glance)
3. [Quick Start & Deployment](#quick-start--deployment)
4. [Environment Variables](#environment-variables)
5. [Version History](#version-history)
6. [Maintenance Notes](#maintenance-notes)
7. [Detailed Documentation Reference](#detailed-documentation-reference)

---

## Customizations At A Glance

### Security & Access Control

**PDF Editor Superuser Restriction** — Optionally restrict PDF editing to superusers only, preventing accidental modifications by regular users. Disabled by default; when enabled, superusers can edit ANY document's PDF regardless of ownership. Defense in depth with both backend validation and frontend hiding.
→ [Details](docs/rkc/pdf-editor-restriction.md)

### Collaborative Features

**Global Saved Views** — Organization-wide saved views visible to all users by setting `owner_id = NULL`. Includes a full management UI for superusers (Settings > Saved Views), toggle switches for personal ↔ global conversion, drag-drop reordering in sidebar and dashboard, and system-wide ordering stored in `ApplicationConfiguration`. Angular signal-based reactivity ensures reliable dashboard loading.
→ [Details](docs/rkc/global-saved-views.md)

### UI Customization Defaults

**Theme Color, Language & Appearance Defaults** — Set organization-wide defaults for theme color, dark mode thumbnail inversion, UI language, and unsaved changes warnings via environment variables. All work as fallbacks without overriding existing user preferences. Also adds 4 date+time format options and fixes card views to respect the user's date format setting.
→ [Details](docs/rkc/ui-defaults.md)

### Mail System

**Universal SMTP & Microsoft Graph API Integration** — Complete mail system overhaul providing:
- **Universal SMTP sending** for all account types (OAuth2 XOAUTH2 + traditional)
- **Microsoft Graph API** for Outlook accounts (bypasses M365 Security Defaults blocking SMTP)
- **Multi-mailbox** access via delegated permissions using a single OAuth app
- **App-only send mode** (`PAPERLESS_OUTLOOK_OAUTH_USE_APP_SEND`) — Graph API sends via `client_credentials` token, enabling sending from any licensed personal mailbox without per-user Exchange delegation
- **Connection pooling** via Celery Beat to eliminate OAuth2 authentication storms
- **Smart correspondent matching** using RFC 5322 format with email-based three-tier matching
- **Email metadata capture** into custom fields (UID, From, Sender, Subject, Date)
- **Email Date: header as document created date** — attachments and .eml files get their `created` date set from the email's `Date:` header instead of OCR text or today's date
- **"Process all mails"** action for read+unread without modifying mail state
- **Processed mail UI** with server-side filtering, error modals, Mail UID column, select-all-in-database, pagination fix
- **Correspondent matching algorithm** consistency between mail-created and UI-created correspondents
- **Mail send webhook** — every outgoing email (workflow and manual) POSTs a full JSON payload (all fields + base64 attachments) to a configurable endpoint; outcome appended as a second line in the send note

→ [Details](docs/rkc/mail-system.md) | [MS365 OAuth Setup](MS365_OAUTH_SETUP.md)

### Document Processing

**AI OCR via Post-Consumption Script** — Replaces Tesseract OCR output with higher-quality text from an AI OCR provider (Mistral OCR, Azure Document Intelligence, or any LiteLLM-compatible OCR model) without modifying the paperless-ngx source code. Implemented as a `PAPERLESS_POST_CONSUME_SCRIPT` hook — zero changes to paperless-ngx itself. Sends the archived PDF as a base64 data URL to LiteLLM's `/v1/ocr` endpoint (native endpoint, not the Mistral pass-through, so cost tracking works). The `content` field is overwritten via `PATCH /api/documents/{id}/`; the search index auto-updates. Email documents (`message/rfc822`) are skipped entirely — they do not benefit from OCR and skipping prevents a race condition with the send-mail pipeline. Disabled by default via `AI_OCR_ENABLED`.
→ [Details](docs/rkc/ai-ocr.md)

**Duplicate Document Re-Add** — When a duplicate is detected during consumption, the existing document's `added` date is reset so it surfaces in the inbox again. Uses two-tier deduplication: MD5 checksum for binary-identical files (PDFs, images) and Mail UID custom field lookup for EML documents whose byte representation varies across fetches. Supports optional tagging, informational notes with source context (mail metadata or source type), and trashed document handling (restore-readd-optionally-retrash). Disabled by default.
→ [Details](docs/rkc/duplicate-readd.md)

### Workflow Enhancements

**Dynamic Workflow Email Templates** — Jinja2 templating for all 6 email fields (subject, body, to, from, cc, bcc) with custom field value placeholders. Includes HTML auto-detection, email validation with error tagging, and a fix for the upstream bug where `to` wasn't templated. New model fields: `from_address`, `cc`, `bcc`, `error_tag`. Templates referencing custom fields that are not yet set when the workflow fires log a warning and skip the send instead of propagating an HTTP 500.
→ [Details](docs/rkc/workflow-email.md)

### Custom Field Enhancements

**Custom Field Filter Buttons** — Quick filter buttons for custom field values on document detail page and card views. Works with all 10 field data types including null/empty values. Card views optionally show "FieldName: Value" format via environment variable.
→ [Details](docs/rkc/custom-field-filters.md)

### Troubleshooting & Debugging

**SSO Debug Logging** — Verbose django-allauth debug logging via `PAPERLESS_DEBUG_SSO` without full DEBUG mode. Includes automatic UiSettings creation for new SSO users (post_save signal) to prevent login errors.
→ [Details](docs/rkc/sso-debug.md)

### Bug Fixes

- **Webhook Docker Hostname Fix** — Fixes upstream bug where workflow webhooks targeting Docker internal hostnames are blocked even when `PAPERLESS_WEBHOOKS_ALLOW_INTERNAL_REQUESTS` is `true`
- **Dashboard Race Condition** — Signal-based reactivity fix for empty dashboard on direct URL access
- **Card Views Date Format** — Card views now respect user's date format preference
- **Processed Mail Pagination** — Fixed pagination showing only one page regardless of total count
- **Bootstrap Tooltip Dark Mode** — Fixed unreadable tooltips in dark mode
- **SSO UiSettings Auto-Creation** — Prevents login errors for new SSO users

→ [Details](docs/rkc/bug-fixes.md)

---

## Quick Start & Deployment

### Setting Environment Variables

All RKC environment variables are optional with sensible defaults. Add to your deployment:

**Docker Compose** (`docker-compose.yml` or `.env`):
```yaml
services:
  webserver:
    environment:
      PAPERLESS_UI_THEME_COLOR: "#2563eb"
      PAPERLESS_UI_DEFAULT_LANGUAGE: "de-de"
      PAPERLESS_CONSUMER_READD_DOCUMENTS: "true"
```

**Bare Metal** (export or systemd):
```bash
export PAPERLESS_UI_THEME_COLOR="#2563eb"
export PAPERLESS_UI_DEFAULT_LANGUAGE="de-de"
```

### Applying Changes

- **Environment variables**: Restart the container/service — no rebuild needed
- **Code modifications**: Rebuild frontend (`cd src-ui && npm run build`), collect static files, restart backend
- **User preferences**: Existing user preferences are never overridden by env var defaults

### Rebuilding Frontend

```bash
# Docker
docker compose build

# Bare Metal
cd src-ui && npm install && npm run build && cd ..
python3 manage.py collectstatic --clear --no-input

# Development
cd src-ui && npm run start  # http://localhost:4200
```

---

## Environment Variables

Complete reference with types and defaults. → [Full details](docs/rkc/environment-variables.md)

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `PAPERLESS_PDF_EDITOR_RESTRICT_TO_SUPERUSER` | Bool | `false` | Restrict PDF editor to superusers |
| `PAPERLESS_UI_THEME_COLOR` | String | `#17541f` | Default theme color |
| `PAPERLESS_UI_DARK_MODE_THUMB_INVERTED` | Bool | `true` | Dark mode thumbnail inversion |
| `PAPERLESS_UI_DEFAULT_LANGUAGE` | String | `de-de` | Default UI language |
| `PAPERLESS_SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE_DEFAULT` | Bool | `true` | Unsaved changes warning |
| `PAPERLESS_SHOW_CUSTOM_FIELD_NAMES_IN_CARDS` | Bool | `false` | Field names in card views |
| `PAPERLESS_DEBUG_SSO` | Bool | `false` | SSO debug logging |
| `PAPERLESS_MAIL_CORRESPONDENT_MATCHING_ALGORITHM` | Int | `6` | Mail correspondent matching |
| `PAPERLESS_MAIL_UID_FIELD` | String | `"Mail UID"` | Mail UID custom field name |
| `PAPERLESS_MAIL_FROM_FIELD` | String | `"Mail From"` | Mail From custom field name |
| `PAPERLESS_MAIL_SENDER_FIELD` | String | `"Mail Sender"` | Mail Sender custom field name |
| `PAPERLESS_MAIL_SUBJECT_FIELD` | String | `"Mail Subject"` | Mail Subject custom field name |
| `PAPERLESS_MAIL_DATE_FIELD` | String | `"Mail Date"` | Mail Date custom field name |
| `PAPERLESS_OUTLOOK_OAUTH_USE_APP_SEND` | Bool | `false` | Use app-only (client_credentials) Graph API send mode for personal mailboxes |
| `PAPERLESS_OUTLOOK_OAUTH_TENANT_ID` | String | — | Azure AD tenant ID required for app-only send mode |
| `AI_OCR_ENABLED` | Bool | `false` | Enable AI OCR post-consume replacement |
| `AI_OCR_URL` | String | — | LiteLLM proxy base URL |
| `AI_OCR_KEY` | String | — | LiteLLM virtual API key |
| `AI_OCR_MODEL` | String | `mistral-ocr-latest` | OCR model name |
| `AI_OCR_TAG_ID` | Int | None | Tag ID to apply on successful AI OCR |
| `PAPERLESS_API_TOKEN` | String | — | Paperless API token for AI OCR script |
| `PAPERLESS_CONSUMER_READD_DOCUMENTS` | Bool | `false` | Enable duplicate re-add |
| `PAPERLESS_CONSUMER_READD_TAG_ID` | Int | None | Tag ID for re-added documents |
| `PAPERLESS_CONSUMER_READD_ADD_NOTE` | Bool | `true` | Add note on re-add |
| `PAPERLESS_CONSUMER_READD_RETRASH` | Bool | `false` | Re-trash after re-add |
| `PAPERLESS_MAIL_SEND_SUCCESS_TAG_ID` | Int | None | Tag ID to apply when workflow email sends successfully |
| `PAPERLESS_MAIL_SEND_FAILURE_TAG_ID` | Int | None | Tag ID to apply when workflow email fails to send |
| `PAPERLESS_MAIL_SEND_ADD_NOTE` | Bool | `false` | Attach a system note on every send attempt |
| `PAPERLESS_MAIL_VERIFY_RECIPIENT` | String | `"dns"` | Recipient domain verification for workflow emails (`none`/`dns`/`dns+smtp`) |
| `PAPERLESS_MAIL_TO_FIELD` | String | `""` | CF name to pre-fill the To field in the manual send dialog |
| `PAPERLESS_MAIL_CC_FIELD` | String | `""` | CF name to pre-fill the CC field in the manual send dialog |
| `PAPERLESS_MAIL_BCC_FIELD` | String | `""` | CF name to pre-fill the BCC field in the manual send dialog |
| `PAPERLESS_MAIL_BODY_FIELD` | String | `""` | CF name to pre-fill the message body in the manual send dialog |
| `PAPERLESS_MAIL_SEND_WEBHOOK_URL` | String | `""` | URL to POST full email payload to after every successful send |
| `PAPERLESS_MAIL_SEND_WEBHOOK_TOKEN` | String | `""` | Token value sent in the webhook auth header |
| `PAPERLESS_MAIL_SEND_WEBHOOK_TOKEN_HEADER` | String | `"Authorization"` | HTTP header name used to carry the webhook token |


---

## Version History

- **v1.4.1** — AI OCR skips email documents (`message/rfc822`) to prevent race condition with send-mail pipeline; workflow email action catches `Jinja2 UndefinedError` so templates referencing unresolved custom fields log a warning and skip instead of propagating HTTP 500
- **v1.4.0** — Mail send webhook: every outgoing email POSTs full JSON payload (all fields + base64 attachments + `document_id` per attachment) to `PAPERLESS_MAIL_SEND_WEBHOOK_URL`; webhook outcome appended as second line of send note when `PAPERLESS_MAIL_SEND_ADD_NOTE` is enabled
- **v1.3.1** — Workflow email notes always attributed to a valid user: `document.owner` or the system `consumer` user for ownerless documents, preventing 500 errors on `GET /api/documents/{id}/`
- **v1.3.0** — Enhanced manual send email dialog: From/CC/BCC fields, custom field pre-fill from document CF values, recipient domain verification and send feedback (tags+notes) now applied to manual sends
- **v1.2.10** — App-only (client_credentials) Graph API send mode for personal mailboxes: `PAPERLESS_OUTLOOK_OAUTH_USE_APP_SEND` + `PAPERLESS_OUTLOOK_OAUTH_TENANT_ID`; requires `Mail.Send` APPLICATION permission + admin consent
- **v1.2.9** — Recipient domain verification for workflow emails: DNS MX check (default) with optional SMTP port 25 probe (`dns+smtp`); admin check script at `scripts/check_smtp_port25.py`
- **v1.2.8** — Mail send feedback: apply success/failure tags and optional system note on every workflow email send attempt

- **v1.2.7** — Graph API shared mailbox Sent Items: `sendMail` endpoint scoped to shared mailbox when `from_email` differs from account username
- **v1.2.6** — WebSocket upload progress UI hang fix (missing `not owner_id` check in server-side _can_view)
- **v1.2.5** — AI OCR post-consumption script: replaces Tesseract content with Mistral/Azure OCR via LiteLLM `/v1/ocr`
- **v1.2.4** — Opaque S/MIME signed message support (smime.p7m) via OpenSSL CMS unwrap; shared MIME walking helper
- **v1.2.3** — Detached S/MIME signed message support (smime.p7s) for Graph API mail retrieval
- **v1.2.2** — Mail consumption sets document `created` from email `Date:` header
- **v1.2.1** — Duplicate Document Re-Add with two-tier dedup (MD5 + Mail UID for EML), tagging, notes, and trashed document handling
- **v1.2.0** — Dynamic Workflow Email with Jinja2 templating for all 6 fields, HTML auto-detection, error tagging
- **v1.1.1** — Webhook Docker hostname validation fix
- **v1.1.0** — Mail System overhaul: Universal SMTP, Graph API, multi-mailbox, connection pooling, UI/UX
- **v1.0.29** — Saved views unsaved changes warning default
- **v1.0.28** — Mail correspondent matching algorithm consistency fix
- **v1.0.27** — Smart correspondent matching (FROM_SMART with email-based three-tier matching)
- **v1.0.26** — Email metadata custom fields (From, Sender, Subject, Date)
- **v1.0.25** — Custom field names and filter buttons in card views
- **v1.0.24** — Processed mail "select all in database" with deletion
- **v1.0.23** — Dashboard saved views race condition fix (Angular signals)
- **v1.0.22** — Card views respect user date format preference (bug fix)
- **v1.0.21** — Date+time format options for user preferences
- **v1.0.20** — Mail UID column in processed mail overview
- **v1.0.19** — Mail action "Process all mails (read and unread)"
- **v1.0.18** — OAuth2 Email Sending Support
- **v1.0.17** — Mail action connection pooling (Celery Beat)
- **v1.0.16** — Server-side filtering for Processed Mail
- **v1.0.15** — Client-side Processed Mail filtering
- **v1.0.14** — Processed mail error modal and date+time columns
- **v1.0.13** — Processed mail pagination fix
- **v1.0.12** — Mail-document correlation via IMAP UID custom field
- **v1.0.11** — System-wide global view ordering with drag-drop
- **v1.0.10** — Toggle switches for personal/global view conversion
- **v1.0.9** — Global saved views management UI
- **v1.0.8** — PDF Editor restriction made optional via env var
- **v1.0.7** — PDF Editor ownership fix (superusers can edit any document)
- **v1.0.6** — Global saved views ordering and custom field filter buttons
- **v1.0.5** — SSO UiSettings comprehensive fix with auto-creation signal
- **v1.0.4** — SSO UiSettings bug fix (deprecated by v1.0.5)
- **v1.0.3** — Social account debug logging
- **v1.0.2** — Default language environment variable
- **v1.0.1** — Theme color and dark mode thumbnail defaults
- **v1.0.0** — Initial: PDF editor restriction, shared saved views

---

## Maintenance Notes

### When Upgrading Paperless-ngx

1. **Search for `RKC:` markers** before applying updates — all custom code is tagged
2. **Review key files**: `src/documents/views.py`, `src/documents/signals/handlers.py`, `src/documents/consumer.py`, `src/paperless_mail/mail.py`, `src/paperless_mail/mail_oauth.py`, `src/paperless_mail/mail_graph.py`, `src/paperless_mail/mail_graph_retrieval.py`
3. **Test customizations** after upgrade (PDF editor, saved views, mail system, workflow emails)
4. **Update this documentation** if customizations change

### Dependencies
- Django permissions system (superuser flag)
- Angular permissions service (`PermissionsService.isSuperUser()`)
- Existing saved view, custom field, and filter infrastructure
- django-allauth (SSO)
- Microsoft Graph API (Outlook mail)

---

## Detailed Documentation Reference

| Document | Content |
|----------|---------|
| [`docs/rkc/pdf-editor-restriction.md`](docs/rkc/pdf-editor-restriction.md) | PDF Editor superuser restriction — env var, backend/frontend implementation, security model |
| [`docs/rkc/global-saved-views.md`](docs/rkc/global-saved-views.md) | Shared views (NULL owner), ordering, management UI, drag-drop, toggle switches, dashboard fix |
| [`docs/rkc/ui-defaults.md`](docs/rkc/ui-defaults.md) | Theme color, dark mode thumbnails, default language, unsaved changes warning, date+time formats |
| [`docs/rkc/sso-debug.md`](docs/rkc/sso-debug.md) | SSO debug logging, UiSettings auto-creation for SSO users |
| [`docs/rkc/custom-field-filters.md`](docs/rkc/custom-field-filters.md) | Filter buttons on document detail page + card views, field name display |
| [`docs/rkc/ai-ocr.md`](docs/rkc/ai-ocr.md) | AI OCR post-consumption hook — LiteLLM `/v1/ocr`, Mistral/Azure providers, cost tracking, Docker Compose setup |
| [`docs/rkc/duplicate-readd.md`](docs/rkc/duplicate-readd.md) | Duplicate document re-add with tagging, notes, trash handling |
| [`docs/rkc/mail-system.md`](docs/rkc/mail-system.md) | Universal SMTP, Graph API, multi-mailbox, OAuth2, connection pooling, smart correspondents, metadata, processed mail UI |
| [`docs/rkc/workflow-email.md`](docs/rkc/workflow-email.md) | Dynamic workflow email templates with Jinja2, HTML auto-detection, error tagging |
| [`docs/rkc/bug-fixes.md`](docs/rkc/bug-fixes.md) | Webhook hostname fix, dashboard race condition, card date format, tooltip dark mode, pagination |
| [`docs/rkc/environment-variables.md`](docs/rkc/environment-variables.md) | Complete reference table of ALL RKC environment variables |

### Related Documentation

- [Paperless-ngx Official Docs](https://docs.paperless-ngx.com/)
- [MS365 OAuth Setup Guide](MS365_OAUTH_SETUP.md)

---

*This documentation should be updated whenever new RKC customizations are added or existing ones are modified.*
