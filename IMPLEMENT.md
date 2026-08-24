# IMPLEMENT.md

## GOAL

Add "Select all across pages" functionality to the management lists (Correspondents, Tags, Document Types, Storage Paths). Currently, the checkbox in the table header only selects items on the current page. The new feature adds a Gmail-style "Select all N items" link in the footer when items are selected, allowing bulk operations on all matching items regardless of pagination.

## ANALYSIS

The backend API (`StandardPagination`) already returns all matching IDs in every paginated response via the `all` field. The frontend `Results<T>` interface already has `all: number[]`. This means we can implement "select all" with zero additional API calls.

The document list already has a "Select all" feature via `DocumentListViewService.selectAll()`. We follow a similar pattern in the shared `ManagementListComponent` base class, which all management lists inherit from.

## IMPLEMENTATION PLAN

### Modified Files

1. `src-ui/src/app/components/manage/management-list/management-list.component.ts` — Add `allObjectIds` property, `selectAll()` method, `isAllSelected` getter, capture `c.all` in `reloadData()`
2. `src-ui/src/app/components/manage/management-list/management-list.component.html` — Add "Select all" link in footer area
3. `src-ui/src/app/components/manage/management-list/management-list.component.spec.ts` — Add tests for new functionality
4. `RKC_CUSTOMIZATIONS.md` — Version entry

---

## Previous Task

Make the email sending system resilient to transient failures (OAuth token refresh failures, Graph API timeouts, etc.) by implementing a persistent email queue with exponential backoff retry. Failed emails must be queued and retried automatically until they succeed or are abandoned after configurable max attempts. No emails should be silently lost.

## ANALYSIS

### Root Cause

The error `OAuth2 token refresh failed` was a transient failure in `refresh_account_oauth_token()` (oauth.py:106) that propagated through `OutlookGraphEmailBackend.send_messages()` (mail_graph.py:107) through `send_email()` (documents/mail.py:375) to `email_action()` (handlers.py:1390). The exception was caught, a failure note was written, and the email was permanently abandoned with no retry.

### Current Architecture Gap

There is zero retry logic in the email sending pipeline. A single transient failure equals permanent failure. The email_action() function fires once during a workflow trigger; if sending fails, it records the failure and moves on.

### Existing Pattern to Follow

The codebase already has a proven pending-actions queue pattern:
- ProcessedMail model with status PENDING_POST_ACTION
- apply_pending_mail_actions() Celery Beat task that processes pending items
- batch_mail_actions_by_account() for pooled connection processing
- Exponential backoff via PAPERLESS_EMAIL_TASK_CRON schedule (default every 10 min)

### Two Send Paths to Fix

1. Workflow emails (email_action() in handlers.py): triggered by document workflows, runs inside Celery task bulk_action(). On failure, the email is permanently abandoned.
2. Manual sends (email_documents() in views.py): triggered by user via REST API POST /api/documents/email/. On failure, returns HTTP 500.

Both call send_email() in documents/mail.py.

### Key Design Decisions

- Re-render templates on retry: Store raw Jinja2 template strings, not rendered values. Re-render with fresh document context on each attempt.
- Attachments via document_id: Store document_id and include_document flag. On retry, rebuild attachments from the document source_path.
- Inline retries: Add 2 quick inline retries (2s, 4s delays) in send_email() for transient blips. Only queue to database if inline retries fail.
- Duplicate send risk is acceptable: Graph API returns 202 (async queue); duplicates are rare and acceptable vs. lost emails.
- Template errors = immediate abandon: Jinja2 UndefinedError and validation failures are not transient; abandoned immediately.
- Manual sends: queue for retry silently, return 202 to user.
- Workflow feedback: immediate failure tag/note remains. Queue processor creates success tag/note when retry succeeds.

## IMPLEMENTATION PLAN

### New Files

1. src/documents/email_queue.py (approx 180 lines) - PendingEmail model + queue processing
2. Migration for PendingEmail model

### Modified Files

3. src/documents/mail.py - Add inline retry to send_email()
4. src/documents/signals/handlers.py - email_action() queues on failure
5. src/documents/views.py - email_documents() queues on failure
6. src/paperless/settings.py - New env vars + beat schedule entry
7. docs/rkc/mail-system.md - New queue section
8. docs/rkc/environment-variables.md - New env vars
9. RKC_CUSTOMIZATIONS.md - Version entry + env vars table
10. STRUCTURE.md - File listing

### PendingEmail Model (email_queue.py)

Fields:
- action FK to WorkflowActionEmail (SET_NULL, nullable, NULL for manual sends)
- document FK to Document (SET_NULL, nullable, NULL if doc deleted)
- 6 template string fields: subject, body, to, from_address, cc, bcc
- is_html, include_document booleans
- rendered_to - pre-computed TO string for notes
- attempts, max_attempts ints
- next_retry_at datetime
- last_error text
- status choices: PENDING / SENDING / SENT / ABANDONED
- created_at, updated_at auto fields
- Custom manager: PendingEmail.pending() filtered to status=PENDING and next_retry_at<=now
- Index on (status, next_retry_at) for efficient queue polling

### Retry Backoff

Formula: min(base_seconds * 2^attempts, max_seconds)
Defaults: base=300s (5min), max=86400s (24h), max_attempts=50 (covers approx 5 days)

### Settings

- PAPERLESS_MAIL_RETRY_MAX_ATTEMPTS (int, default=50)
- PAPERLESS_MAIL_RETRY_BASE_SECONDS (int, default=300)
- PAPERLESS_MAIL_RETRY_MAX_SECONDS (int, default=86400)
- Beat schedule: task documents.email_queue.process_pending_emails with PAPERLESS_MAIL_QUEUE_CRON (default every 5 min)

### Core Functions in email_queue.py

- calculate_next_retry(attempts) - exponential backoff calculation
- enqueue_failed_email(action, document, rendered_to, error_msg) - capture template strings, create PendingEmail
- process_pending_emails() - @shared_task Celery task, iterates pending emails with rate limiting
- _process_single_pending_email(pending) - re-render templates, rebuild attachments, call send_email(), handle success/failure/abandon
- _re_render_and_send(pending) - shared helper for template re-rendering and send attempt

## PHASE 8: Admin UI for Email Queue

### Overview

Add a dialog-based admin UI for viewing and managing the PendingEmail queue, accessible from the Mail Settings page. Follows the exact same pattern as the existing Processed Mail dialog.

### Backend Changes

#### New: PendingEmailSerializer (documents/serialisers.py or email_queue.py)
- Fields: id, action, document, subject_template, rendered_to, status, attempts, max_attempts, next_retry_at, last_error, created_at, updated_at
- Read-only viewset serializer

#### New: PendingEmailFilterSet (documents/filters.py or email_queue.py)
- filter_text CharFilter for server-side text search across: subject_template, rendered_to, last_error, status
- status exact filter

#### New: PendingEmailViewSet (documents/views.py or email_queue.py)
- Read-only model viewset (list + retrieve)
- Custom bulk_delete action (same pattern as ProcessedMailViewSet)
- StandardPagination, DjangoFilterBackend, OrderingFilter
- Permission: IsAuthenticated + superuser (or PaperlessObjectPermissions)
- Registered at /api/pending_email/ in paperless/urls.py

### Frontend Changes

#### New: PendingEmail interface (src-ui/src/app/data/pending-email.ts)
- Fields: id, action, document, subject_template, rendered_to, status, attempts, max_attempts, next_retry_at, last_error, created_at, updated_at

#### New: PendingEmailService (src-ui/src/app/services/rest/pending-email.service.ts)
- Extends AbstractPaperlessService<PendingEmail>
- resourceName = 'pending_email'
- bulk_delete() and bulk_delete_filtered() methods

#### New: PendingEmailDialogComponent (src-ui/src/app/components/manage/mail/pending-email-dialog/)
- ts + html + scss files
- Modal dialog (same pattern as ProcessedMailDialogComponent)
- Table columns: Subject, Recipients, Status, Attempts, Next Retry, Last Error, Created
- Server-side text filtering with debounced input
- Status filter dropdown (PENDING, SENDING, ABANDONED)
- Checkbox selection with select-all-in-page
- Delete selected / Delete all filtered
- Error popover for long last_error text
- Pagination with collectionSize

#### Modified: mail.component.ts + mail.component.html
- Import PendingEmailDialogComponent
- Add viewPendingEmails() method
- Add button in header area: "Email Queue" with inbox icon
- Permission check: PendingEmail view permission

#### Modified: permissions.service.ts
- Add PendingEmail = '%s_pendingemail' to PermissionType enum

#### Modified: urls.py
- Register PendingEmailViewSet at 'pending_email'

### Button Placement

The "Email Queue" button goes in the mail page header area, NOT per-rule. It sits alongside the page header or as a standalone section between accounts and rules. The queue is global (not per-rule).

Suggested HTML placement: After the mail accounts section, before the mail rules section. A small row with:
  <button class="btn btn-sm btn-outline-warning" (click)="viewPendingEmails()">
    <i-bs name="inbox"></i-bs> Email Queue ({{ pendingEmailCount }})
  </button>

Where pendingEmailCount is loaded on init via PendingEmailService.listFiltered({status: 'PENDING'}).count.
